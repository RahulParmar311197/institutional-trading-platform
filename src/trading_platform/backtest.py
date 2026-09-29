from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from trading_platform.decision import DecisionAction, TradingDecision
from trading_platform.paper import Position
from trading_platform.paper_engine import PaperTradingEngine
from trading_platform.pipeline import ReplayStrategyPipeline
from trading_platform.recorded_events import RecordedMarketEvent, normalize_recorded_events
from trading_platform.risk import RiskDecisionType, RiskEngine
from trading_platform.strategy import StrategyEvaluator

BASIS_POINTS = Decimal("10000")


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


@dataclass(frozen=True, slots=True)
class EquityPoint:
    event_id: str
    mark_price: Decimal
    equity: Decimal
    drawdown: Decimal
    drawdown_pct: Decimal


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

    def run(self, events: list[RecordedMarketEvent]) -> BacktestResult:
        normalized = normalize_recorded_events(events)
        if not normalized:
            raise ValueError("backtest requires at least one recorded event")

        instrument_ids = {event.instrument_id for event in normalized}
        if len(instrument_ids) != 1:
            raise ValueError("minimal backtester supports exactly one instrument")
        instrument_id = normalized[0].instrument_id

        pipeline = ReplayStrategyPipeline(
            instrument_id=instrument_id,
            interval=self.interval,
            strategy=self.strategy,
        )
        paper = PaperTradingEngine(risk_engine=self.risk_engine)
        steps = pipeline.run(list(normalized))
        trades: list[BacktestTrade] = []
        equity_curve: list[EquityPoint] = []
        rejected = 0
        total_fees = Decimal("0")
        peak_equity = self.starting_equity

        for event, step in zip(normalized, steps, strict=True):
            decision = step.decision
            if decision is not None and decision.directional:
                previous_position = paper.broker.positions.get(instrument_id)
                realized_before = (
                    previous_position.realized_pnl
                    if previous_position is not None
                    else Decimal("0")
                )
                fill_price = self.assumptions.fill_price(decision)
                execution = paper.execute_market(
                    decision,
                    requested_quantity=self.requested_quantity,
                    fill_id=f"backtest:{step.event_id}:{len(trades)}",
                    fill_price=fill_price,
                )
                if execution.risk_decision.decision is not RiskDecisionType.APPROVE:
                    rejected += 1
                else:
                    if execution.order is None or execution.position is None:
                        raise RuntimeError(
                            "approved backtest execution did not produce order and position"
                        )
                    fee = self.assumptions.fee_per_filled_order
                    total_fees += fee
                    realized_delta = execution.position.realized_pnl - realized_before
                    trades.append(
                        BacktestTrade(
                            event_id=step.event_id,
                            action=decision.action,
                            quantity=execution.order.filled_quantity,
                            reference_price=decision.reference_price,
                            fill_price=fill_price,
                            fee=fee,
                            realized_pnl_delta=realized_delta,
                            realized_pnl_after=execution.position.realized_pnl,
                        )
                    )

            position = paper.broker.positions.get(instrument_id, Position())
            unrealized = (
                position.unrealized_pnl(event.price)
                if position.quantity
                else Decimal("0")
            )
            equity = (
                self.starting_equity
                + position.realized_pnl
                + unrealized
                - total_fees
            )
            peak_equity = max(peak_equity, equity)
            drawdown = peak_equity - equity
            drawdown_pct = drawdown / peak_equity
            equity_curve.append(
                EquityPoint(
                    event_id=event.event_id,
                    mark_price=event.price,
                    equity=equity,
                    drawdown=drawdown,
                    drawdown_pct=drawdown_pct,
                )
            )

        position = paper.broker.positions.get(instrument_id, Position())
        final_mark = normalized[-1].price
        unrealized = (
            position.unrealized_pnl(final_mark)
            if position.quantity
            else Decimal("0")
        )
        net_pnl = position.realized_pnl + unrealized - total_fees
        final_equity = self.starting_equity + net_pnl
        metrics = _calculate_metrics(
            trades=trades,
            equity_curve=equity_curve,
            starting_equity=self.starting_equity,
            final_equity=final_equity,
        )
        return BacktestResult(
            trades=tuple(trades),
            equity_curve=tuple(equity_curve),
            metrics=metrics,
            rejected_decisions=rejected,
            final_position_quantity=position.quantity,
            final_position_average_price=position.average_price,
            realized_pnl=position.realized_pnl,
            unrealized_pnl=unrealized,
            total_fees=total_fees,
            net_pnl=net_pnl,
            final_equity=final_equity,
        )


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
