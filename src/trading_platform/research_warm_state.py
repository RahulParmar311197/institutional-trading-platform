import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from trading_platform.backtest import EventDrivenBacktester
from trading_platform.candles import Candle
from trading_platform.pipeline import ReplayPipelineState, ReplayStrategyPipeline
from trading_platform.recorded_events import RecordedMarketEvent, normalize_recorded_events
from trading_platform.research_periods import ResearchWindow, WalkForwardFold
from trading_platform.research_state import (
    ResearchStateKind,
    ResearchStateProvenance,
)

PIPELINE_WARM_STATE_VERSION = 1
PIPELINE_WARM_STATE_MAX_BYTES = 8 * 1024 * 1024
_WARM_STATE_FIELDS = frozenset(
    {"version", "strategy_id", "instrument_id", "interval_microseconds", "closed_candles"}
)
_CANDLE_FIELDS = frozenset(
    {"instrument_id", "start", "end", "open", "high", "low", "close", "volume", "closed"}
)


@dataclass(frozen=True, slots=True)
class PipelineWarmState:
    strategy_id: str
    instrument_id: uuid.UUID
    interval: timedelta
    closed_candles: tuple[Candle, ...]
    version: int = PIPELINE_WARM_STATE_VERSION

    def __post_init__(self) -> None:
        if self.version != PIPELINE_WARM_STATE_VERSION:
            raise ValueError("unsupported pipeline warm-state version")
        if not self.strategy_id.strip():
            raise ValueError("warm-state strategy_id must not be empty")
        if self.interval <= timedelta(0):
            raise ValueError("warm-state interval must be positive")
        if not self.closed_candles:
            raise ValueError("warm state requires at least one closed candle")

        previous_end: datetime | None = None
        for candle in self.closed_candles:
            _validate_candle(candle, instrument_id=self.instrument_id, interval=self.interval)
            if previous_end is not None and candle.start < previous_end:
                raise ValueError("warm-state candles must be ordered and non-overlapping")
            previous_end = candle.end

    @classmethod
    def from_pipeline(cls, pipeline: ReplayStrategyPipeline) -> "PipelineWarmState":
        strategy_id = pipeline.strategy.strategy_id
        if not strategy_id.strip():
            raise ValueError("warm-state export requires a stable strategy_id")
        return cls(
            strategy_id=strategy_id,
            instrument_id=pipeline.instrument_id,
            interval=pipeline.interval,
            closed_candles=pipeline.closed_candles,
        )

    def to_bytes(self) -> bytes:
        payload = {
            "version": self.version,
            "strategy_id": self.strategy_id,
            "instrument_id": str(self.instrument_id),
            "interval_microseconds": _timedelta_microseconds(self.interval),
            "closed_candles": [_candle_payload(candle) for candle in self.closed_candles],
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        if len(encoded) > PIPELINE_WARM_STATE_MAX_BYTES:
            raise ValueError("pipeline warm state exceeds maximum size")
        return encoded

    @classmethod
    def from_bytes(cls, payload: bytes) -> "PipelineWarmState":
        if not payload:
            raise ValueError("pipeline warm state must not be empty")
        if len(payload) > PIPELINE_WARM_STATE_MAX_BYTES:
            raise ValueError("pipeline warm state exceeds maximum size")
        try:
            raw = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid pipeline warm-state JSON") from exc
        root = _require_object(raw, _WARM_STATE_FIELDS, "pipeline warm state")
        interval_microseconds = _require_int(root, "interval_microseconds")
        if interval_microseconds <= 0:
            raise ValueError("warm-state interval_microseconds must be positive")
        try:
            instrument_id = uuid.UUID(_require_str(root, "instrument_id"))
        except ValueError as exc:
            raise ValueError("warm-state instrument_id must be a UUID") from exc
        candles_raw = root["closed_candles"]
        if not isinstance(candles_raw, list):
            raise ValueError("warm-state closed_candles must be a list")
        return cls(
            version=_require_int(root, "version"),
            strategy_id=_require_str(root, "strategy_id"),
            instrument_id=instrument_id,
            interval=timedelta(microseconds=interval_microseconds),
            closed_candles=tuple(_candle_from_payload(item) for item in candles_raw),
        )

    @property
    def state_digest(self) -> str:
        return hashlib.sha256(self.to_bytes()).hexdigest()

    def apply_to_pipeline(self, pipeline: ReplayStrategyPipeline) -> None:
        if pipeline.strategy.strategy_id != self.strategy_id:
            raise ValueError("warm-state strategy does not match replay pipeline")
        if pipeline.instrument_id != self.instrument_id:
            raise ValueError("warm-state instrument does not match replay pipeline")
        if pipeline.interval != self.interval:
            raise ValueError("warm-state interval does not match replay pipeline")
        current = pipeline.checkpoint_state()
        if current.closed_candles or current.pending_trades:
            raise ValueError("warm state may only be applied to a fresh replay pipeline")
        pipeline.restore_state(
            ReplayPipelineState(
                closed_candles=self.closed_candles,
                pending_trades=(),
            )
        )


@dataclass(frozen=True, slots=True)
class PreparedWarmState:
    provenance: ResearchStateProvenance
    state: PipelineWarmState

    def __post_init__(self) -> None:
        if self.provenance.kind is not ResearchStateKind.WARMUP:
            raise ValueError("prepared warm state requires WARMUP provenance")
        if self.provenance.strategy_id != self.state.strategy_id:
            raise ValueError("warm-state provenance strategy does not match state")
        if self.provenance.state_digest != self.state.state_digest:
            raise ValueError("warm-state provenance digest does not match serialized state")
        if any(
            candle.start < self.provenance.source_window.start
            or candle.end > self.provenance.source_window.end
            for candle in self.state.closed_candles
        ):
            raise ValueError("warm-state candle history must be confined to source_window")

    @property
    def preparation_state_id(self) -> str:
        return self.provenance.provenance_id


def prepare_pipeline_warm_state(
    backtester: EventDrivenBacktester,
    source_events: list[RecordedMarketEvent],
    *,
    boundary_id: str,
    fold: WalkForwardFold,
    source_window: ResearchWindow,
    feature_ids: tuple[str, ...] = (),
) -> PreparedWarmState:
    normalized = normalize_recorded_events(source_events)
    if not normalized:
        raise ValueError("warm-state preparation requires source events")
    if any(not source_window.contains(event.exchange_timestamp) for event in normalized):
        raise ValueError("warm-state source events must be confined to source_window")
    instrument_ids = {event.instrument_id for event in normalized}
    if len(instrument_ids) != 1:
        raise ValueError("warm-state preparation supports exactly one instrument")

    pipeline = ReplayStrategyPipeline(
        instrument_id=normalized[0].instrument_id,
        interval=backtester.interval,
        strategy=backtester.strategy,
    )
    pipeline.run(list(normalized))
    state = PipelineWarmState.from_pipeline(pipeline)
    serialized_state = state.to_bytes()
    provenance = ResearchStateProvenance.from_events(
        kind=ResearchStateKind.WARMUP,
        boundary_id=boundary_id,
        fold=fold,
        strategy_id=backtester.strategy.strategy_id,
        feature_ids=feature_ids,
        source_window=source_window,
        source_events=list(normalized),
        serialized_state=serialized_state,
    )
    return PreparedWarmState(provenance=provenance, state=state)


def _validate_candle(
    candle: Candle,
    *,
    instrument_id: uuid.UUID,
    interval: timedelta,
) -> None:
    if candle.instrument_id != instrument_id:
        raise ValueError("warm-state candle instrument does not match state")
    if not candle.closed:
        raise ValueError("warm state may contain closed candles only")
    if candle.start.tzinfo is None or candle.start.utcoffset() is None:
        raise ValueError("warm-state candle start must be timezone-aware")
    if candle.end.tzinfo is None or candle.end.utcoffset() is None:
        raise ValueError("warm-state candle end must be timezone-aware")
    if candle.end - candle.start != interval:
        raise ValueError("warm-state candle duration does not match interval")
    if candle.open <= 0 or candle.high <= 0 or candle.low <= 0 or candle.close <= 0:
        raise ValueError("warm-state candle prices must be positive")
    if candle.low > min(candle.open, candle.close) or candle.high < max(
        candle.open, candle.close
    ):
        raise ValueError("warm-state candle OHLC values are incoherent")
    if candle.low > candle.high:
        raise ValueError("warm-state candle low must not exceed high")
    if candle.volume <= 0:
        raise ValueError("warm-state candle volume must be positive")


def _candle_payload(candle: Candle) -> dict[str, object]:
    return {
        "instrument_id": str(candle.instrument_id),
        "start": candle.start.isoformat(),
        "end": candle.end.isoformat(),
        "open": _decimal_identity(candle.open),
        "high": _decimal_identity(candle.high),
        "low": _decimal_identity(candle.low),
        "close": _decimal_identity(candle.close),
        "volume": candle.volume,
        "closed": candle.closed,
    }


def _candle_from_payload(value: Any) -> Candle:
    raw = _require_object(value, _CANDLE_FIELDS, "warm-state candle")
    try:
        instrument_id = uuid.UUID(_require_str(raw, "instrument_id"))
    except ValueError as exc:
        raise ValueError("warm-state candle instrument_id must be a UUID") from exc
    try:
        start = datetime.fromisoformat(_require_str(raw, "start"))
        end = datetime.fromisoformat(_require_str(raw, "end"))
    except ValueError as exc:
        raise ValueError("warm-state candle timestamps must be ISO-8601") from exc
    return Candle(
        instrument_id=instrument_id,
        start=start,
        end=end,
        open=_require_decimal(raw, "open"),
        high=_require_decimal(raw, "high"),
        low=_require_decimal(raw, "low"),
        close=_require_decimal(raw, "close"),
        volume=_require_int(raw, "volume"),
        closed=_require_bool(raw, "closed"),
    )


def _require_object(
    value: Any,
    fields: frozenset[str],
    name: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{name} has invalid fields")
    if any(not isinstance(key, str) for key in value):
        raise ValueError(f"{name} keys must be strings")
    return value


def _require_str(payload: dict[str, Any], key: str) -> str:
    value = payload[key]
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _require_int(payload: dict[str, Any], key: str) -> int:
    value = payload[key]
    if type(value) is not int:
        raise ValueError(f"{key} must be an integer")
    return value


def _require_bool(payload: dict[str, Any], key: str) -> bool:
    value = payload[key]
    if type(value) is not bool:
        raise ValueError(f"{key} must be a boolean")
    return value


def _require_decimal(payload: dict[str, Any], key: str) -> Decimal:
    value = payload[key]
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a decimal string")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{key} must be a decimal string") from exc
    if not result.is_finite():
        raise ValueError(f"{key} must be finite")
    return result


def _timedelta_microseconds(value: timedelta) -> int:
    return (value.days * 86_400 + value.seconds) * 1_000_000 + value.microseconds


def _decimal_identity(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == 0:
        return "0"
    return format(normalized, "f")
