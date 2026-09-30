import hashlib
import json
from dataclasses import dataclass

from trading_platform.backtest import EventDrivenBacktester
from trading_platform.recorded_events import RecordedMarketEvent
from trading_platform.research_selection import (
    SelectionDecision,
    SelectionFold,
    select_validation_candidate,
)
from trading_platform.research_validation import (
    ResearchCandidate,
    ValidationBacktestResult,
    ValidationObjective,
    evaluate_fixed_strategy_validation_fold,
    score_validation_result,
)


@dataclass(frozen=True, slots=True)
class ValidationSearchResult:
    candidate_set_id: str
    selection_fold_id: str
    objective: ValidationObjective
    evaluations: tuple[ValidationBacktestResult, ...]
    decision: SelectionDecision

    def __post_init__(self) -> None:
        if not self.candidate_set_id.strip():
            raise ValueError("candidate_set_id must not be empty")
        if not self.evaluations:
            raise ValueError("validation search requires at least one evaluation")
        candidate_ids = tuple(result.candidate.candidate_id for result in self.evaluations)
        if candidate_ids != tuple(sorted(candidate_ids)):
            raise ValueError("validation search evaluations must be ordered by candidate_id")
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("validation search candidate IDs must be unique")
        if self.decision.selection_fold_id != self.selection_fold_id:
            raise ValueError("validation search decision belongs to a different selection fold")
        if self.decision.objective_id != self.objective.value:
            raise ValueError("validation search decision uses a different objective")
        if self.decision.direction is not self.objective.direction:
            raise ValueError("validation search decision uses a different direction")
        decision_ids = tuple(sorted(score.candidate_id for score in self.decision.candidates))
        if decision_ids != candidate_ids:
            raise ValueError("validation search decision does not cover the candidate set")

    @property
    def search_id(self) -> str:
        payload = {
            "candidate_set_id": self.candidate_set_id,
            "selection_fold_id": self.selection_fold_id,
            "objective_id": self.objective.value,
            "decision_id": self.decision.decision_id,
            "validation_result_ids": [result.result_id for result in self.evaluations],
        }
        return _identity("validation_search_v1", payload)


def run_validation_search(
    backtesters: tuple[EventDrivenBacktester, ...],
    events: list[RecordedMarketEvent],
    *,
    boundary_id: str,
    selection_fold: SelectionFold,
    objective: ValidationObjective,
    feature_ids: tuple[str, ...] = (),
) -> ValidationSearchResult:
    if not backtesters:
        raise ValueError("validation search requires at least one backtester")

    indexed: list[tuple[str, EventDrivenBacktester]] = []
    for backtester in backtesters:
        candidate = ResearchCandidate.from_backtester(
            backtester,
            feature_ids=feature_ids,
        )
        indexed.append((candidate.candidate_id, backtester))

    candidate_ids = tuple(candidate_id for candidate_id, _ in indexed)
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("validation search backtesters must have unique candidate identities")

    ordered = sorted(indexed, key=lambda item: item[0])
    evaluations = tuple(
        evaluate_fixed_strategy_validation_fold(
            backtester,
            events,
            boundary_id=boundary_id,
            selection_fold=selection_fold,
            feature_ids=feature_ids,
        )
        for _, backtester in ordered
    )
    scores = tuple(
        score_validation_result(result, objective=objective) for result in evaluations
    )
    decision = select_validation_candidate(
        selection_fold,
        objective_id=objective.value,
        direction=objective.direction,
        candidates=scores,
    )
    ordered_candidate_ids = tuple(result.candidate.candidate_id for result in evaluations)
    return ValidationSearchResult(
        candidate_set_id=_candidate_set_identity(ordered_candidate_ids),
        selection_fold_id=selection_fold.selection_fold_id,
        objective=objective,
        evaluations=evaluations,
        decision=decision,
    )


def _candidate_set_identity(candidate_ids: tuple[str, ...]) -> str:
    return _identity("validation_candidate_set_v1", {"candidate_ids": candidate_ids})


def _identity(prefix: str, payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(encoded).hexdigest()}"
