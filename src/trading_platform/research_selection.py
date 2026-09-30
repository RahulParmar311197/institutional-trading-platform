import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, timedelta
from decimal import Decimal
from enum import StrEnum

from trading_platform.research_periods import ResearchWindow, WalkForwardFold

SELECTION_SPEC_VERSION = 1
SELECTION_DECISION_VERSION = 1


class ObjectiveDirection(StrEnum):
    MAXIMIZE = "MAXIMIZE"
    MINIMIZE = "MINIMIZE"


@dataclass(frozen=True, slots=True)
class SelectionSpec:
    validation_length: timedelta
    embargo: timedelta = timedelta(0)
    version: int = SELECTION_SPEC_VERSION

    def __post_init__(self) -> None:
        if self.version != SELECTION_SPEC_VERSION:
            raise ValueError("unsupported selection specification version")
        if self.validation_length <= timedelta(0):
            raise ValueError("validation_length must be positive")
        if self.embargo < timedelta(0):
            raise ValueError("selection embargo must be non-negative")

    @property
    def spec_id(self) -> str:
        return (
            f"selection_v{self.version}_"
            f"validation{_timedelta_microseconds(self.validation_length)}_"
            f"embargo{_timedelta_microseconds(self.embargo)}"
        )


@dataclass(frozen=True, slots=True)
class SelectionFold:
    parent_fold_id: str
    parent_fold_spec_id: str
    fit: ResearchWindow
    validation: ResearchWindow
    test: ResearchWindow
    selection_spec_id: str

    def __post_init__(self) -> None:
        for name, value in (
            ("parent_fold_id", self.parent_fold_id),
            ("parent_fold_spec_id", self.parent_fold_spec_id),
            ("selection_spec_id", self.selection_spec_id),
        ):
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        if self.fit.end > self.validation.start:
            raise ValueError("fit and validation windows must not overlap")
        if self.validation.end > self.test.start:
            raise ValueError("validation and test windows must not overlap")

    @property
    def selection_fold_id(self) -> str:
        payload = {
            "parent_fold_id": self.parent_fold_id,
            "parent_fold_spec_id": self.parent_fold_spec_id,
            "selection_spec_id": self.selection_spec_id,
            "fit": _window_payload(self.fit),
            "validation": _window_payload(self.validation),
            "test": _window_payload(self.test),
        }
        return _identity("selection_fold", payload)


@dataclass(frozen=True, slots=True)
class ValidationCandidateScore:
    selection_fold_id: str
    candidate_id: str
    validation_result_id: str
    objective_id: str
    direction: ObjectiveDirection
    score: Decimal

    def __post_init__(self) -> None:
        for name, value in (
            ("selection_fold_id", self.selection_fold_id),
            ("candidate_id", self.candidate_id),
            ("validation_result_id", self.validation_result_id),
            ("objective_id", self.objective_id),
        ):
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        if not self.score.is_finite():
            raise ValueError("validation score must be finite")


@dataclass(frozen=True, slots=True)
class SelectionDecision:
    selection_fold_id: str
    objective_id: str
    direction: ObjectiveDirection
    candidates: tuple[ValidationCandidateScore, ...]
    selected_candidate_id: str
    version: int = SELECTION_DECISION_VERSION

    def __post_init__(self) -> None:
        if self.version != SELECTION_DECISION_VERSION:
            raise ValueError("unsupported selection decision version")
        if not self.selection_fold_id.strip():
            raise ValueError("selection_fold_id must not be empty")
        if not self.objective_id.strip():
            raise ValueError("objective_id must not be empty")
        if not self.candidates:
            raise ValueError("selection decision requires candidate validation scores")
        candidate_ids = tuple(candidate.candidate_id for candidate in self.candidates)
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("candidate validation scores must have unique candidate_id values")
        result_ids = tuple(candidate.validation_result_id for candidate in self.candidates)
        if len(set(result_ids)) != len(result_ids):
            raise ValueError(
                "candidate validation scores must have unique validation_result_id values"
            )
        if any(
            candidate.selection_fold_id != self.selection_fold_id
            for candidate in self.candidates
        ):
            raise ValueError("candidate validation score belongs to a different selection fold")
        if any(candidate.objective_id != self.objective_id for candidate in self.candidates):
            raise ValueError("candidate validation score uses a different objective")
        if any(candidate.direction is not self.direction for candidate in self.candidates):
            raise ValueError("candidate validation score uses a different objective direction")
        if self.selected_candidate_id not in candidate_ids:
            raise ValueError("selected_candidate_id must reference a candidate validation score")

    @property
    def decision_id(self) -> str:
        payload = {
            "version": self.version,
            "selection_fold_id": self.selection_fold_id,
            "objective_id": self.objective_id,
            "direction": self.direction.value,
            "selected_candidate_id": self.selected_candidate_id,
            "candidates": [
                {
                    "candidate_id": candidate.candidate_id,
                    "validation_result_id": candidate.validation_result_id,
                    "score": _decimal_identity(candidate.score),
                }
                for candidate in sorted(self.candidates, key=lambda item: item.candidate_id)
            ],
        }
        return _identity(f"selection_decision_v{self.version}", payload)


def split_fold_for_selection(
    fold: WalkForwardFold,
    *,
    spec: SelectionSpec,
) -> SelectionFold:
    validation_end = fold.train.end
    validation_start = validation_end - spec.validation_length
    fit_end = validation_start - spec.embargo
    if fit_end <= fold.train.start:
        raise ValueError("selection specification leaves no positive fit window")

    return SelectionFold(
        parent_fold_id=fold.fold_id,
        parent_fold_spec_id=fold.spec_id,
        fit=ResearchWindow(start=fold.train.start, end=fit_end),
        validation=ResearchWindow(start=validation_start, end=validation_end),
        test=fold.test,
        selection_spec_id=spec.spec_id,
    )


def select_validation_candidate(
    selection_fold: SelectionFold,
    *,
    objective_id: str,
    direction: ObjectiveDirection,
    candidates: tuple[ValidationCandidateScore, ...],
) -> SelectionDecision:
    if not candidates:
        raise ValueError("candidate validation scores must not be empty")
    if any(
        candidate.selection_fold_id != selection_fold.selection_fold_id
        for candidate in candidates
    ):
        raise ValueError("candidate validation score belongs to a different selection fold")
    if any(candidate.objective_id != objective_id for candidate in candidates):
        raise ValueError("candidate validation score uses a different objective")
    if any(candidate.direction is not direction for candidate in candidates):
        raise ValueError("candidate validation score uses a different objective direction")

    ordered = sorted(candidates, key=lambda candidate: candidate.candidate_id)
    selected = ordered[0]
    for candidate in ordered[1:]:
        if direction is ObjectiveDirection.MAXIMIZE:
            if candidate.score > selected.score:
                selected = candidate
        elif candidate.score < selected.score:
            selected = candidate

    return SelectionDecision(
        selection_fold_id=selection_fold.selection_fold_id,
        objective_id=objective_id,
        direction=direction,
        candidates=candidates,
        selected_candidate_id=selected.candidate_id,
    )


def _identity(prefix: str, payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(encoded).hexdigest()}"


def _window_payload(window: ResearchWindow) -> dict[str, str]:
    return {
        "start": window.start.astimezone(UTC).isoformat(),
        "end": window.end.astimezone(UTC).isoformat(),
    }


def _timedelta_microseconds(value: timedelta) -> int:
    return (value.days * 86_400 + value.seconds) * 1_000_000 + value.microseconds


def _decimal_identity(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == 0:
        return "0"
    return format(normalized, "f")
