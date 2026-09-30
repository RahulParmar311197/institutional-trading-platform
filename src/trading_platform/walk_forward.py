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
