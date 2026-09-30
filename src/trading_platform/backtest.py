import hashlib
import json
import os
import tempfile
import uuid
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from trading_platform.candles import Candle, CandleBuilder, Trade
from trading_platform.decision import DecisionAction, TradingDecision
from trading_platform.paper import Position
from trading_platform.paper_engine import PaperTradingEngine
from trading_platform.pipeline import ReplayPipelineState, ReplayStrategyPipeline
from trading_platform.recorded_events import RecordedMarketEvent, normalize_recorded_events
from trading_platform.replay import ReplayCheckpoint, ReplayStream
from trading_platform.risk import RiskDecisionType, RiskEngine
from trading_platform.strategy import SignalDirection, StrategyEvaluator

BASIS_POINTS = Decimal("10000")
BACKTEST_CHECKPOINT_VERSION = 1
BACKTEST_CHECKPOINT_MAX_BYTES = 32 * 1024 * 1024
_BACKTEST_CHECKPOINT_FIELDS = frozenset(
    {
        "version",
        "replay",
        "config_digest",
        "pipeline_state",
        "position",
        "trades",
        "equity_curve",
        "rejected_decisions",
        "total_fees",
        "peak_equity",
    }
)


@dataclass(frozen=True, slots=True)
class ExecutionAssumptions:
    slippage_bps: Decimal = Decimal("0")
    fee_per_filled_order: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if self.slippage_bps < 0 or self.slippage_bps >= BASIS_POINTS:
            raise ValueError("slippage_bps must be in [0, 10000)")
        if self.fee_per_filled_order < 0:
            raise ValueError("fee_per_filled_order must be non-negative")

    def fill_price(self, decision: TradingDecision) -> Decimal:
        slippage_fraction = self.slippage_bps / BASIS_POINTS
        if decision.action is DecisionAction.LONG:
            return decision.reference_price * (Decimal("1") + slippage_fraction)
        if decision.action is DecisionAction.SHORT:
            return decision.reference_price * (Decimal("1") - slippage_fraction)
        raise ValueError("fill price requires a directional decision")


@dataclass(frozen=True, slots=True)
class BacktestTrade:
    event_id: str
    action: DecisionAction
    quantity: int
    reference_price: Decimal
    fill_price: Decimal
    fee: Decimal
    realized_pnl_delta: Decimal
    realized_pnl_after: Decimal

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("backtest trade event_id must not be empty")
        if self.action not in {DecisionAction.LONG, DecisionAction.SHORT}:
            raise ValueError("backtest trade action must be directional")
        if self.quantity <= 0:
            raise ValueError("backtest trade quantity must be positive")
        if self.reference_price <= 0 or self.fill_price <= 0:
            raise ValueError("backtest trade prices must be positive")
        if self.fee < 0:
            raise ValueError("backtest trade fee must be non-negative")


@dataclass(frozen=True, slots=True)
class EquityPoint:
    event_id: str
    mark_price: Decimal
    equity: Decimal
    drawdown: Decimal
    drawdown_pct: Decimal

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("equity point event_id must not be empty")
        if self.mark_price <= 0:
            raise ValueError("equity point mark_price must be positive")
        if self.drawdown < 0 or self.drawdown_pct < 0:
            raise ValueError("equity point drawdown values must be non-negative")


@dataclass(frozen=True, slots=True)
class BacktestMetrics:
    total_return: Decimal
    max_drawdown: Decimal
    max_drawdown_pct: Decimal
    trade_count: int
    winning_realizations: int
    losing_realizations: int
    gross_profit: Decimal
    gross_loss: Decimal
    profit_factor: Decimal | None


@dataclass(frozen=True, slots=True)
class BacktestResult:
    trades: tuple[BacktestTrade, ...]
    equity_curve: tuple[EquityPoint, ...]
    metrics: BacktestMetrics
    rejected_decisions: int
    final_position_quantity: int
    final_position_average_price: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_fees: Decimal
    net_pnl: Decimal
    final_equity: Decimal


@dataclass(frozen=True, slots=True)
class PositionSnapshot:
    quantity: int
    average_price: Decimal
    realized_pnl: Decimal

    def __post_init__(self) -> None:
        if self.quantity == 0 and self.average_price != 0:
            raise ValueError("flat checkpoint position must have zero average price")
        if self.quantity != 0 and self.average_price <= 0:
            raise ValueError("open checkpoint position requires positive average price")

    @classmethod
    def from_position(cls, position: Position) -> "PositionSnapshot":
        return cls(
            quantity=position.quantity,
            average_price=position.average_price,
            realized_pnl=position.realized_pnl,
        )

    def to_position(self) -> Position:
        return Position(
            quantity=self.quantity,
            average_price=self.average_price,
            realized_pnl=self.realized_pnl,
        )


@dataclass(frozen=True, slots=True)
class BacktestCheckpoint:
    replay: ReplayCheckpoint
    config_digest: str
    pipeline_state: ReplayPipelineState
    position: PositionSnapshot
    trades: tuple[BacktestTrade, ...]
    equity_curve: tuple[EquityPoint, ...]
    rejected_decisions: int
    total_fees: Decimal
    peak_equity: Decimal
    version: int = BACKTEST_CHECKPOINT_VERSION

    def __post_init__(self) -> None:
        if self.version != BACKTEST_CHECKPOINT_VERSION:
            raise ValueError("unsupported backtest checkpoint version")
        _validate_digest(self.config_digest, "backtest config_digest")
        if self.rejected_decisions < 0:
            raise ValueError("backtest rejected_decisions must be non-negative")
        if self.total_fees < 0:
            raise ValueError("backtest total_fees must be non-negative")
        if self.peak_equity <= 0:
            raise ValueError("backtest peak_equity must be positive")
        if len(self.equity_curve) != self.replay.cursor:
            raise ValueError("backtest equity curve length must equal replay cursor")
        _validate_checkpoint_internal_state(self)

    def to_json(self) -> str:
        payload = {
            "version": self.version,
            "replay": json.loads(self.replay.to_json()),
            "config_digest": self.config_digest,
            "pipeline_state": {
                "closed_candles": [
                    _candle_to_payload(candle)
                    for candle in self.pipeline_state.closed_candles
                ],
                "pending_trades": [
                    _trade_to_payload(trade)
                    for trade in self.pipeline_state.pending_trades
                ],
            },
            "position": {
                "quantity": self.position.quantity,
                "average_price": str(self.position.average_price),
                "realized_pnl": str(self.position.realized_pnl),
            },
            "trades": [_backtest_trade_to_payload(trade) for trade in self.trades],
            "equity_curve": [_equity_point_to_payload(point) for point in self.equity_curve],
            "rejected_decisions": self.rejected_decisions,
            "total_fees": str(self.total_fees),
            "peak_equity": str(self.peak_equity),
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, payload: str) -> "BacktestCheckpoint":
        try:
            raw = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid backtest checkpoint JSON") from exc
        root = _require_object(raw, _BACKTEST_CHECKPOINT_FIELDS, "backtest checkpoint")
        version = _require_int(root, "version")
        replay_raw = root["replay"]
        replay = ReplayCheckpoint.from_json(
            json.dumps(replay_raw, sort_keys=True, separators=(",", ":"))
        )
        pipeline_raw = _require_object(
            root["pipeline_state"],
            frozenset({"closed_candles", "pending_trades"}),
            "pipeline_state",
        )
        closed_raw = _require_list(pipeline_raw, "closed_candles")
        pending_raw = _require_list(pipeline_raw, "pending_trades")
        position_raw = _require_object(
            root["position"],
            frozenset({"quantity", "average_price", "realized_pnl"}),
            "position",
        )
        trades_raw = _require_list(root, "trades")
        equity_raw = _require_list(root, "equity_curve")
        return cls(
            version=version,
            replay=replay,
            config_digest=_require_str(root, "config_digest"),
            pipeline_state=ReplayPipelineState(
                closed_candles=tuple(_candle_from_payload(item) for item in closed_raw),
                pending_trades=tuple(_trade_from_payload(item) for item in pending_raw),
            ),
            position=PositionSnapshot(
                quantity=_require_int(position_raw, "quantity"),
                average_price=_require_decimal(position_raw, "average_price"),
                realized_pnl=_require_decimal(position_raw, "realized_pnl"),
            ),
            trades=tuple(_backtest_trade_from_payload(item) for item in trades_raw),
            equity_curve=tuple(_equity_point_from_payload(item) for item in equity_raw),
            rejected_decisions=_require_int(root, "rejected_decisions"),
            total_fees=_require_decimal(root, "total_fees"),
            peak_equity=_require_decimal(root, "peak_equity"),
        )


class BacktestCheckpointFileStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if not self.path.name:
            raise ValueError("checkpoint path must name a file")

    def load(self) -> BacktestCheckpoint | None:
        try:
            with self.path.open("rb") as handle:
                payload = handle.read(BACKTEST_CHECKPOINT_MAX_BYTES + 1)
        except FileNotFoundError:
            return None
        if len(payload) > BACKTEST_CHECKPOINT_MAX_BYTES:
            raise ValueError("backtest checkpoint file exceeds maximum size")
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("backtest checkpoint file must be valid UTF-8") from exc
        return BacktestCheckpoint.from_json(text)

    def save(self, checkpoint: BacktestCheckpoint) -> None:
        payload = (checkpoint.to_json() + "\n").encode("utf-8")
        if len(payload) > BACKTEST_CHECKPOINT_MAX_BYTES:
            raise ValueError("backtest checkpoint exceeds maximum size")
        parent = self.path.parent
        parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=parent
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, self.path)
            _fsync_directory(parent)
        except BaseException:
            with suppress(FileNotFoundError):
                os.unlink(temporary_name)
            raise

    def clear(self) -> bool:
        try:
            self.path.unlink()
        except FileNotFoundError:
            return False
        _fsync_directory(self.path.parent)
        return True


class EventDrivenBacktester:
    def __init__(
        self,
        *,
        interval: timedelta,
        strategy: StrategyEvaluator,
        risk_engine: RiskEngine,
        requested_quantity: int,
        starting_equity: Decimal,
        assumptions: ExecutionAssumptions | None = None,
    ) -> None:
        if interval <= timedelta(0):
            raise ValueError("interval must be positive")
        if requested_quantity <= 0:
            raise ValueError("requested_quantity must be positive")
        if starting_equity <= 0:
            raise ValueError("starting_equity must be positive")
        self.interval = interval
        self.strategy = strategy
        self.risk_engine = risk_engine
        self.requested_quantity = requested_quantity
        self.starting_equity = starting_equity
        self.assumptions = assumptions or ExecutionAssumptions()

    def create_session(
        self,
        events: list[RecordedMarketEvent],
        *,
        checkpoint: BacktestCheckpoint | None = None,
    ) -> "BacktestSession":
        normalized = normalize_recorded_events(events)
        if not normalized:
            raise ValueError("backtest requires at least one recorded event")
        instrument_ids = {event.instrument_id for event in normalized}
        if len(instrument_ids) != 1:
            raise ValueError("minimal backtester supports exactly one instrument")
        session = BacktestSession(backtester=self, events=normalized)
        if checkpoint is not None:
            session.restore(checkpoint)
        return session

    def run(self, events: list[RecordedMarketEvent]) -> BacktestResult:
        return self.create_session(events).run_to_completion()

    def checkpoint_config_digest(self) -> str:
        strategy_id = getattr(self.strategy, "strategy_id", None)
        if not isinstance(strategy_id, str) or not strategy_id.strip():
            raise ValueError("checkpointing requires strategy with stable strategy_id")
        controls = self.risk_engine.controls
        payload = {
            "interval_seconds": str(self.interval.total_seconds()),
            "strategy_type": (
                f"{type(self.strategy).__module__}.{type(self.strategy).__qualname__}"
            ),
            "strategy_id": strategy_id,
            "requested_quantity": self.requested_quantity,
            "starting_equity": str(self.starting_equity),
            "slippage_bps": str(self.assumptions.slippage_bps),
            "fee_per_filled_order": str(self.assumptions.fee_per_filled_order),
            "max_order_notional": str(self.risk_engine.limits.max_order_notional),
            "max_position_notional": str(
                self.risk_engine.limits.max_position_notional
            ),
            "operational_mode": controls.mode.value,
            "risk_locks": sorted(
                (
                    {
                        "scope": lock.scope.value,
                        "key": lock.key,
                        "reason": lock.reason,
                    }
                    for lock in controls.locks
                ),
                key=lambda item: (
                    item["scope"],
                    item["key"] or "",
                    item["reason"],
                ),
            ),
        }
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class BacktestSession:
    def __init__(
        self,
        *,
        backtester: EventDrivenBacktester,
        events: tuple[RecordedMarketEvent, ...],
    ) -> None:
        self.backtester = backtester
        self.events = events
        self.instrument_id = events[0].instrument_id
        self.replay = ReplayStream(events=events)
        self.pipeline = ReplayStrategyPipeline(
            instrument_id=self.instrument_id,
            interval=backtester.interval,
            strategy=backtester.strategy,
        )
        self.paper = PaperTradingEngine(risk_engine=backtester.risk_engine)
        self.trades: list[BacktestTrade] = []
        self.equity_curve: list[EquityPoint] = []
        self.rejected_decisions = 0
        self.total_fees = Decimal("0")
        self.peak_equity = backtester.starting_equity

    @property
    def complete(self) -> bool:
        return self.replay.remaining == 0

    def step(self, count: int = 1) -> int:
        if count <= 0:
            raise ValueError("count must be positive")
        processed = 0
        while processed < count and (event := self.replay.next_event()) is not None:
            pipeline_step = self.pipeline.process_event(event)
            self._apply_step(event, pipeline_step.decision)
            processed += 1
        return processed

    def run_to_completion(self) -> BacktestResult:
        self.step(max(1, self.replay.remaining))
        return self.result()

    def checkpoint(self) -> BacktestCheckpoint:
        position = self.paper.broker.positions.get(self.instrument_id, Position())
        return BacktestCheckpoint(
            replay=self.replay.checkpoint(),
            config_digest=self.backtester.checkpoint_config_digest(),
            pipeline_state=self.pipeline.checkpoint_state(),
            position=PositionSnapshot.from_position(position),
            trades=tuple(self.trades),
            equity_curve=tuple(self.equity_curve),
            rejected_decisions=self.rejected_decisions,
            total_fees=self.total_fees,
            peak_equity=self.peak_equity,
        )

    def restore(self, checkpoint: BacktestCheckpoint) -> None:
        expected_config = self.backtester.checkpoint_config_digest()
        if checkpoint.config_digest != expected_config:
            raise ValueError("backtest checkpoint configuration does not match backtester")

        candidate_replay = ReplayStream(events=self.events)
        candidate_replay.restore(checkpoint.replay)
        candidate_pipeline = ReplayStrategyPipeline(
            instrument_id=self.instrument_id,
            interval=self.backtester.interval,
            strategy=self.backtester.strategy,
        )
        candidate_pipeline.restore_state(checkpoint.pipeline_state)
        _validate_checkpoint_against_session(
            checkpoint=checkpoint,
            events=self.events,
            instrument_id=self.instrument_id,
            backtester=self.backtester,
        )

        candidate_paper = PaperTradingEngine(risk_engine=self.backtester.risk_engine)
        if checkpoint.position.quantity != 0 or checkpoint.position.realized_pnl != 0:
            candidate_paper.broker.positions[self.instrument_id] = (
                checkpoint.position.to_position()
            )

        self.replay = candidate_replay
        self.pipeline = candidate_pipeline
        self.paper = candidate_paper
        self.trades = list(checkpoint.trades)
        self.equity_curve = list(checkpoint.equity_curve)
        self.rejected_decisions = checkpoint.rejected_decisions
        self.total_fees = checkpoint.total_fees
        self.peak_equity = checkpoint.peak_equity

    def result(self) -> BacktestResult:
        if not self.complete:
            raise ValueError("backtest result requires a completed session")
        position = self.paper.broker.positions.get(self.instrument_id, Position())
        final_mark = self.events[-1].price
        unrealized = (
            position.unrealized_pnl(final_mark)
            if position.quantity
            else Decimal("0")
        )
        net_pnl = position.realized_pnl + unrealized - self.total_fees
        final_equity = self.backtester.starting_equity + net_pnl
        metrics = _calculate_metrics(
            trades=self.trades,
            equity_curve=self.equity_curve,
            starting_equity=self.backtester.starting_equity,
            final_equity=final_equity,
        )
        return BacktestResult(
            trades=tuple(self.trades),
            equity_curve=tuple(self.equity_curve),
            metrics=metrics,
            rejected_decisions=self.rejected_decisions,
            final_position_quantity=position.quantity,
            final_position_average_price=position.average_price,
            realized_pnl=position.realized_pnl,
            unrealized_pnl=unrealized,
            total_fees=self.total_fees,
            net_pnl=net_pnl,
            final_equity=final_equity,
        )

    def _apply_step(
        self,
        event: RecordedMarketEvent,
        decision: TradingDecision | None,
    ) -> None:
        if decision is not None and decision.directional:
            previous_position = self.paper.broker.positions.get(self.instrument_id)
            realized_before = (
                previous_position.realized_pnl
                if previous_position is not None
                else Decimal("0")
            )
            fill_price = self.backtester.assumptions.fill_price(decision)
            execution = self.paper.execute_market(
                decision,
                requested_quantity=self.backtester.requested_quantity,
                fill_id=f"backtest:{event.event_id}:{len(self.trades)}",
                fill_price=fill_price,
            )
            if execution.risk_decision.decision is not RiskDecisionType.APPROVE:
                self.rejected_decisions += 1
            else:
                if execution.order is None or execution.position is None:
                    raise RuntimeError(
                        "approved backtest execution did not produce order and position"
                    )
                fee = self.backtester.assumptions.fee_per_filled_order
                self.total_fees += fee
                realized_delta = execution.position.realized_pnl - realized_before
                self.trades.append(
                    BacktestTrade(
                        event_id=event.event_id,
                        action=decision.action,
                        quantity=execution.order.filled_quantity,
                        reference_price=decision.reference_price,
                        fill_price=fill_price,
                        fee=fee,
                        realized_pnl_delta=realized_delta,
                        realized_pnl_after=execution.position.realized_pnl,
                    )
                )

        position = self.paper.broker.positions.get(self.instrument_id, Position())
        unrealized = (
            position.unrealized_pnl(event.price)
            if position.quantity
            else Decimal("0")
        )
        equity = (
            self.backtester.starting_equity
            + position.realized_pnl
            + unrealized
            - self.total_fees
        )
        self.peak_equity = max(self.peak_equity, equity)
        drawdown = self.peak_equity - equity
        drawdown_pct = drawdown / self.peak_equity
        self.equity_curve.append(
            EquityPoint(
                event_id=event.event_id,
                mark_price=event.price,
                equity=equity,
                drawdown=drawdown,
                drawdown_pct=drawdown_pct,
            )
        )


def _validate_checkpoint_internal_state(checkpoint: BacktestCheckpoint) -> None:
    if checkpoint.total_fees != sum((trade.fee for trade in checkpoint.trades), Decimal("0")):
        raise ValueError("backtest checkpoint total_fees does not match trades")
    if len(checkpoint.trades) + checkpoint.rejected_decisions > checkpoint.replay.cursor:
        raise ValueError("backtest checkpoint executions exceed processed events")

    rebuilt_position = Position()
    realized_after = Decimal("0")
    trade_event_ids: set[str] = set()
    for trade in checkpoint.trades:
        if trade.event_id in trade_event_ids:
            raise ValueError("backtest checkpoint contains duplicate trade event_id")
        trade_event_ids.add(trade.event_id)
        realized_after += trade.realized_pnl_delta
        if trade.realized_pnl_after != realized_after:
            raise ValueError("backtest checkpoint realized P&L chain is inconsistent")
        direction = (
            SignalDirection.LONG
            if trade.action is DecisionAction.LONG
            else SignalDirection.SHORT
        )
        rebuilt_position.apply_fill(
            direction=direction,
            quantity=trade.quantity,
            price=trade.fill_price,
        )
        if rebuilt_position.realized_pnl != trade.realized_pnl_after:
            raise ValueError("backtest checkpoint trade P&L does not match fills")

    expected_position = PositionSnapshot.from_position(rebuilt_position)
    if checkpoint.position != expected_position:
        raise ValueError("backtest checkpoint position does not match trades")

    equity_event_ids: set[str] = set()
    last_peak: Decimal | None = None
    for point in checkpoint.equity_curve:
        if point.event_id in equity_event_ids:
            raise ValueError("backtest checkpoint contains duplicate equity event_id")
        equity_event_ids.add(point.event_id)
        implied_peak = point.equity + point.drawdown
        if implied_peak <= 0:
            raise ValueError("backtest checkpoint equity implies non-positive peak")
        if point.drawdown_pct != point.drawdown / implied_peak:
            raise ValueError("backtest checkpoint drawdown percentage is inconsistent")
        if last_peak is not None and implied_peak < last_peak:
            raise ValueError("backtest checkpoint peak equity moves backwards")
        last_peak = implied_peak

    if last_peak is not None and checkpoint.peak_equity != last_peak:
        raise ValueError("backtest checkpoint peak_equity is inconsistent")
    if not trade_event_ids.issubset(equity_event_ids):
        raise ValueError("backtest checkpoint trade references unprocessed event")


def _validate_checkpoint_against_session(
    *,
    checkpoint: BacktestCheckpoint,
    events: tuple[RecordedMarketEvent, ...],
    instrument_id: uuid.UUID,
    backtester: EventDrivenBacktester,
) -> None:
    prefix = events[: checkpoint.replay.cursor]
    for event, point in zip(prefix, checkpoint.equity_curve, strict=True):
        if point.event_id != event.event_id or point.mark_price != event.price:
            raise ValueError("backtest checkpoint equity curve does not match replay prefix")

    event_indexes = {event.event_id: index for index, event in enumerate(prefix)}
    previous_trade_index = -1
    for trade in checkpoint.trades:
        event_index = event_indexes.get(trade.event_id)
        if event_index is None or event_index <= previous_trade_index:
            raise ValueError("backtest checkpoint trade ordering does not match replay prefix")
        previous_trade_index = event_index
        if trade.quantity != backtester.requested_quantity:
            raise ValueError("backtest checkpoint trade quantity does not match configuration")
        if trade.fee != backtester.assumptions.fee_per_filled_order:
            raise ValueError("backtest checkpoint trade fee does not match configuration")
        slippage_fraction = backtester.assumptions.slippage_bps / BASIS_POINTS
        multiplier = (
            Decimal("1") + slippage_fraction
            if trade.action is DecisionAction.LONG
            else Decimal("1") - slippage_fraction
        )
        if trade.fill_price != trade.reference_price * multiplier:
            raise ValueError("backtest checkpoint fill price does not match assumptions")

    builder = CandleBuilder(instrument_id, interval=backtester.interval)
    closed_candles: list[Candle] = []
    for event in prefix:
        completed = builder.add(event.to_trade())
        if completed is not None:
            closed_candles.append(completed)
    expected_pipeline = ReplayPipelineState(
        closed_candles=tuple(closed_candles),
        pending_trades=builder.pending_trades,
    )
    if checkpoint.pipeline_state != expected_pipeline:
        raise ValueError("backtest checkpoint pipeline state does not match replay prefix")

    trades_by_event = {trade.event_id: trade for trade in checkpoint.trades}
    position = Position()
    fees = Decimal("0")
    peak_equity = backtester.starting_equity
    for event, point in zip(prefix, checkpoint.equity_curve, strict=True):
        event_trade = trades_by_event.get(event.event_id)
        if event_trade is not None:
            direction = (
                SignalDirection.LONG
                if event_trade.action is DecisionAction.LONG
                else SignalDirection.SHORT
            )
            position.apply_fill(
                direction=direction,
                quantity=event_trade.quantity,
                price=event_trade.fill_price,
            )
            fees += event_trade.fee
        unrealized = (
            position.unrealized_pnl(event.price)
            if position.quantity
            else Decimal("0")
        )
        equity = backtester.starting_equity + position.realized_pnl + unrealized - fees
        peak_equity = max(peak_equity, equity)
        drawdown = peak_equity - equity
        expected_point = EquityPoint(
            event_id=event.event_id,
            mark_price=event.price,
            equity=equity,
            drawdown=drawdown,
            drawdown_pct=drawdown / peak_equity,
        )
        if point != expected_point:
            raise ValueError("backtest checkpoint economic state does not match replay prefix")

    if checkpoint.position != PositionSnapshot.from_position(position):
        raise ValueError("backtest checkpoint final position does not match replay prefix")
    if checkpoint.total_fees != fees or checkpoint.peak_equity != peak_equity:
        raise ValueError("backtest checkpoint aggregate economics do not match replay prefix")


def _calculate_metrics(
    *,
    trades: list[BacktestTrade],
    equity_curve: list[EquityPoint],
    starting_equity: Decimal,
    final_equity: Decimal,
) -> BacktestMetrics:
    realization_deltas = [trade.realized_pnl_delta for trade in trades]
    positive = [value for value in realization_deltas if value > 0]
    negative = [value for value in realization_deltas if value < 0]
    gross_profit = sum(positive, Decimal("0"))
    gross_loss = -sum(negative, Decimal("0"))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else None
    max_drawdown = max((point.drawdown for point in equity_curve), default=Decimal("0"))
    max_drawdown_pct = max(
        (point.drawdown_pct for point in equity_curve),
        default=Decimal("0"),
    )
    return BacktestMetrics(
        total_return=(final_equity - starting_equity) / starting_equity,
        max_drawdown=max_drawdown,
        max_drawdown_pct=max_drawdown_pct,
        trade_count=len(trades),
        winning_realizations=len(positive),
        losing_realizations=len(negative),
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        profit_factor=profit_factor,
    )


def _validate_digest(value: str, name: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")


def _require_object(value: Any, fields: frozenset[str], name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    if frozenset(value) != fields:
        raise ValueError(f"{name} has unexpected fields")
    return value


def _require_list(container: dict[str, Any], key: str) -> list[Any]:
    value = container.get(key)
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list")
    return value


def _require_str(container: dict[str, Any], key: str) -> str:
    value = container.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _require_int(container: dict[str, Any], key: str) -> int:
    value = container.get(key)
    if type(value) is not int:
        raise ValueError(f"{key} must be an integer")
    return value


def _require_bool(container: dict[str, Any], key: str) -> bool:
    value = container.get(key)
    if type(value) is not bool:
        raise ValueError(f"{key} must be a boolean")
    return value


def _require_decimal(container: dict[str, Any], key: str) -> Decimal:
    value = _require_str(container, key)
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{key} must be a decimal string") from exc
    if not result.is_finite():
        raise ValueError(f"{key} must be finite")
    return result


def _require_datetime(container: dict[str, Any], key: str) -> datetime:
    value = _require_str(container, key)
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{key} must be an ISO datetime") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(f"{key} must be timezone-aware")
    return result


def _require_uuid(container: dict[str, Any], key: str) -> uuid.UUID:
    value = _require_str(container, key)
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise ValueError(f"{key} must be a UUID") from exc


def _candle_to_payload(candle: Candle) -> dict[str, Any]:
    return {
        "instrument_id": str(candle.instrument_id),
        "start": candle.start.isoformat(),
        "end": candle.end.isoformat(),
        "open": str(candle.open),
        "high": str(candle.high),
        "low": str(candle.low),
        "close": str(candle.close),
        "volume": candle.volume,
        "closed": candle.closed,
    }


def _candle_from_payload(value: Any) -> Candle:
    raw = _require_object(
        value,
        frozenset(
            {
                "instrument_id",
                "start",
                "end",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "closed",
            }
        ),
        "candle",
    )
    return Candle(
        instrument_id=_require_uuid(raw, "instrument_id"),
        start=_require_datetime(raw, "start"),
        end=_require_datetime(raw, "end"),
        open=_require_decimal(raw, "open"),
        high=_require_decimal(raw, "high"),
        low=_require_decimal(raw, "low"),
        close=_require_decimal(raw, "close"),
        volume=_require_int(raw, "volume"),
        closed=_require_bool(raw, "closed"),
    )


def _trade_to_payload(trade: Trade) -> dict[str, Any]:
    return {
        "instrument_id": str(trade.instrument_id),
        "timestamp": trade.timestamp.isoformat(),
        "price": str(trade.price),
        "quantity": trade.quantity,
    }


def _trade_from_payload(value: Any) -> Trade:
    raw = _require_object(
        value,
        frozenset({"instrument_id", "timestamp", "price", "quantity"}),
        "pending trade",
    )
    return Trade(
        instrument_id=_require_uuid(raw, "instrument_id"),
        timestamp=_require_datetime(raw, "timestamp"),
        price=_require_decimal(raw, "price"),
        quantity=_require_int(raw, "quantity"),
    )


def _backtest_trade_to_payload(trade: BacktestTrade) -> dict[str, Any]:
    return {
        "event_id": trade.event_id,
        "action": trade.action.value,
        "quantity": trade.quantity,
        "reference_price": str(trade.reference_price),
        "fill_price": str(trade.fill_price),
        "fee": str(trade.fee),
        "realized_pnl_delta": str(trade.realized_pnl_delta),
        "realized_pnl_after": str(trade.realized_pnl_after),
    }


def _backtest_trade_from_payload(value: Any) -> BacktestTrade:
    raw = _require_object(
        value,
        frozenset(
            {
                "event_id",
                "action",
                "quantity",
                "reference_price",
                "fill_price",
                "fee",
                "realized_pnl_delta",
                "realized_pnl_after",
            }
        ),
        "backtest trade",
    )
    try:
        action = DecisionAction(_require_str(raw, "action"))
    except ValueError as exc:
        raise ValueError("backtest trade action is invalid") from exc
    if action not in {DecisionAction.LONG, DecisionAction.SHORT}:
        raise ValueError("backtest trade action must be directional")
    return BacktestTrade(
        event_id=_require_str(raw, "event_id"),
        action=action,
        quantity=_require_int(raw, "quantity"),
        reference_price=_require_decimal(raw, "reference_price"),
        fill_price=_require_decimal(raw, "fill_price"),
        fee=_require_decimal(raw, "fee"),
        realized_pnl_delta=_require_decimal(raw, "realized_pnl_delta"),
        realized_pnl_after=_require_decimal(raw, "realized_pnl_after"),
    )


def _equity_point_to_payload(point: EquityPoint) -> dict[str, Any]:
    return {
        "event_id": point.event_id,
        "mark_price": str(point.mark_price),
        "equity": str(point.equity),
        "drawdown": str(point.drawdown),
        "drawdown_pct": str(point.drawdown_pct),
    }


def _equity_point_from_payload(value: Any) -> EquityPoint:
    raw = _require_object(
        value,
        frozenset({"event_id", "mark_price", "equity", "drawdown", "drawdown_pct"}),
        "equity point",
    )
    return EquityPoint(
        event_id=_require_str(raw, "event_id"),
        mark_price=_require_decimal(raw, "mark_price"),
        equity=_require_decimal(raw, "equity"),
        drawdown=_require_decimal(raw, "drawdown"),
        drawdown_pct=_require_decimal(raw, "drawdown_pct"),
    )


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    directory_fd = os.open(path, flags)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
