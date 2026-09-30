import hashlib
import json
from dataclasses import dataclass

from trading_platform.backtest import EventDrivenBacktester
from trading_platform.recorded_events import RecordedMarketEvent, normalize_recorded_events
from trading_platform.replay import ReplayStream
from trading_platform.research_periods import WalkForwardFold
from trading_platform.research_results import OOSBacktestResult, OOSProvenance
from trading_platform.research_selection import SelectionDecision, SelectionFold
from trading_platform.research_validation import ResearchCandidate
from trading_platform.research_warm_state import PreparedWarmState


@dataclass(frozen=True, slots=True)
class SelectedOOSBacktestResult:
    selection_decision_id: str
    candidate_id: str
    oos: OOSBacktestResult

    def __post_init__(self) -> None:
        if not self.selection_decision_id.strip():
            raise ValueError("selection_decision_id must not be empty")
        if not self.candidate_id.strip():
            raise ValueError("candidate_id must not be empty")

    @property
    def result_id(self) -> str:
        payload = {
            "selection_decision_id": self.selection_decision_id,
            "candidate_id": self.candidate_id,
            "oos_result_id": self.oos.result_id,
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        return f"selected_oos_v1_{hashlib.sha256(encoded).hexdigest()}"


@dataclass(frozen=True, slots=True)
class WarmOOSBacktestResult:
    preparation_state_id: str
    oos: OOSBacktestResult

    def __post_init__(self) -> None:
        if not self.preparation_state_id.strip():
            raise ValueError("preparation_state_id must not be empty")

    @property
    def result_id(self) -> str:
        payload = {
            "preparation_state_id": self.preparation_state_id,
            "oos_result_id": self.oos.result_id,
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        return f"warm_oos_v1_{hashlib.sha256(encoded).hexdigest()}"


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
    normalized = _validate_oos_events(events, fold=fold)
    strategy_id = _validated_strategy_id(backtester)
    result = backtester.run(list(normalized))
    return _build_oos_result(
        backtester,
        normalized,
        result=result,
        boundary_id=boundary_id,
        fold=fold,
        strategy_id=strategy_id,
        feature_ids=feature_ids,
    )


def evaluate_warm_strategy_oos_fold(
    backtester: EventDrivenBacktester,
    events: list[RecordedMarketEvent],
    *,
    boundary_id: str,
    fold: WalkForwardFold,
    prepared_state: PreparedWarmState,
    feature_ids: tuple[str, ...] = (),
) -> WarmOOSBacktestResult:
    normalized = _validate_oos_events(events, fold=fold)
    strategy_id = _validated_strategy_id(backtester)
    provenance = prepared_state.provenance

    if provenance.boundary_id != boundary_id:
        raise ValueError("warm-state boundary does not match OOS boundary")
    if provenance.fold_id != fold.fold_id or provenance.fold_spec_id != fold.spec_id:
        raise ValueError("warm state does not belong to the requested OOS fold")
    if provenance.strategy_id != strategy_id:
        raise ValueError("warm-state strategy does not match OOS strategy")
    if provenance.feature_ids != feature_ids:
        raise ValueError("warm-state features do not match OOS features")
    if prepared_state.state.instrument_id != normalized[0].instrument_id:
        raise ValueError("warm-state instrument does not match OOS event stream")
    if prepared_state.state.interval != backtester.interval:
        raise ValueError("warm-state interval does not match OOS backtester")
    if any(candle.end > fold.test.start for candle in prepared_state.state.closed_candles):
        raise ValueError("warm-state candle history reaches into the OOS test window")

    session = backtester.create_session(list(normalized))
    prepared_state.state.apply_to_pipeline(session.pipeline)
    result = session.run_to_completion()
    oos = _build_oos_result(
        backtester,
        normalized,
        result=result,
        boundary_id=boundary_id,
        fold=fold,
        strategy_id=strategy_id,
        feature_ids=feature_ids,
    )
    return WarmOOSBacktestResult(
        preparation_state_id=prepared_state.preparation_state_id,
        oos=oos,
    )


def evaluate_selected_strategy_oos_fold(
    backtester: EventDrivenBacktester,
    events: list[RecordedMarketEvent],
    *,
    boundary_id: str,
    fold: WalkForwardFold,
    selection_fold: SelectionFold,
    decision: SelectionDecision,
    feature_ids: tuple[str, ...] = (),
) -> SelectedOOSBacktestResult:
    if selection_fold.parent_fold_id != fold.fold_id:
        raise ValueError("selection fold does not belong to the requested OOS fold")
    if selection_fold.parent_fold_spec_id != fold.spec_id:
        raise ValueError("selection fold specification does not match OOS fold")
    if selection_fold.test != fold.test:
        raise ValueError("selection fold test window does not match OOS fold")
    if decision.selection_fold_id != selection_fold.selection_fold_id:
        raise ValueError("selection decision does not belong to the selection fold")

    candidate = ResearchCandidate.from_backtester(
        backtester,
        feature_ids=feature_ids,
    )
    if candidate.candidate_id != decision.selected_candidate_id:
        raise ValueError("backtester candidate does not match selected validation candidate")

    oos = evaluate_fixed_strategy_oos_fold(
        backtester,
        events,
        boundary_id=boundary_id,
        fold=fold,
        feature_ids=feature_ids,
    )
    return SelectedOOSBacktestResult(
        selection_decision_id=decision.decision_id,
        candidate_id=candidate.candidate_id,
        oos=oos,
    )


def _validate_oos_events(
    events: list[RecordedMarketEvent],
    *,
    fold: WalkForwardFold,
) -> tuple[RecordedMarketEvent, ...]:
    normalized = normalize_recorded_events(events)
    if not normalized:
        raise ValueError("OOS fold evaluation requires at least one recorded event")
    if any(not fold.test.contains(event.exchange_timestamp) for event in normalized):
        raise ValueError("OOS fold events must be confined to the fold test window")
    return normalized


def _validated_strategy_id(backtester: EventDrivenBacktester) -> str:
    strategy_id = backtester.strategy.strategy_id
    if not strategy_id.strip():
        raise ValueError("OOS fold evaluation requires a stable strategy_id")
    return strategy_id


def _build_oos_result(
    backtester: EventDrivenBacktester,
    normalized: tuple[RecordedMarketEvent, ...],
    *,
    result: object,
    boundary_id: str,
    fold: WalkForwardFold,
    strategy_id: str,
    feature_ids: tuple[str, ...],
) -> OOSBacktestResult:
    from trading_platform.backtest import BacktestResult

    if not isinstance(result, BacktestResult):
        raise TypeError("result must be a BacktestResult")
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
