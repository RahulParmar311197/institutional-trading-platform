from trading_platform.backtest import EventDrivenBacktester
from trading_platform.recorded_events import RecordedMarketEvent, normalize_recorded_events
from trading_platform.replay import ReplayStream
from trading_platform.research_periods import WalkForwardFold
from trading_platform.research_results import OOSBacktestResult, OOSProvenance


def evaluate_fixed_strategy_oos_fold(
    backtester: EventDrivenBacktester,
    events: list[RecordedMarketEvent],
    *,
    boundary_id: str,
    fold: WalkForwardFold,
    feature_ids: tuple[str, ...] = (),
) -> OOSBacktestResult:
    """Evaluate one cold-start OOS fold without training or parameter selection.

    The caller must provide only events from the fold's half-open test window. Events are
    rejected rather than filtered so an accidental train/warmup leak cannot silently alter
    the evaluated state or result provenance.
    """
    normalized = normalize_recorded_events(events)
    if not normalized:
        raise ValueError("OOS fold evaluation requires at least one recorded event")
    if any(not fold.test.contains(event.exchange_timestamp) for event in normalized):
        raise ValueError("OOS fold events must be confined to the fold test window")

    strategy_id = backtester.strategy.strategy_id
    if not strategy_id.strip():
        raise ValueError("OOS fold evaluation requires a stable strategy_id")

    result = backtester.run(list(normalized))
    stream_digest = ReplayStream(events=normalized).stream_digest
    provenance = OOSProvenance.from_fold(
        boundary_id=boundary_id,
        fold=fold,
        strategy_id=strategy_id,
        feature_ids=feature_ids,
        stream_digest=stream_digest,
        backtest_config_digest=backtester.checkpoint_config_digest(),
        assumptions=backtester.assumptions,
    )
    return OOSBacktestResult(provenance=provenance, result=result)
