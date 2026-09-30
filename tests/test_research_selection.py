from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest
from test_backtest import BASE

from trading_platform.research_periods import ResearchWindow, WalkForwardFold
from trading_platform.research_selection import (
    ObjectiveDirection,
    SelectionSpec,
    ValidationCandidateScore,
    select_validation_candidate,
    split_fold_for_selection,
)


def fold() -> WalkForwardFold:
    return WalkForwardFold(
        index=0,
        train=ResearchWindow(
            start=BASE,
            end=BASE + timedelta(days=10),
        ),
        test=ResearchWindow(
            start=BASE + timedelta(days=11),
            end=BASE + timedelta(days=13),
        ),
        spec_id="walk_forward_v1_fixture",
    )


def score(
    *,
    selection_fold_id: str,
    candidate_id: str,
    result_id: str,
    value: str,
    objective_id: str = "mean_return_v1",
    direction: ObjectiveDirection = ObjectiveDirection.MAXIMIZE,
) -> ValidationCandidateScore:
    return ValidationCandidateScore(
        selection_fold_id=selection_fold_id,
        candidate_id=candidate_id,
        validation_result_id=result_id,
        objective_id=objective_id,
        direction=direction,
        score=Decimal(value),
    )


def test_selection_split_keeps_validation_inside_parent_train_and_test_untouched() -> None:
    current_fold = fold()
    selection = split_fold_for_selection(
        current_fold,
        spec=SelectionSpec(
            validation_length=timedelta(days=2),
            embargo=timedelta(hours=12),
        ),
    )

    assert selection.fit.start == current_fold.train.start
    assert selection.fit.end == BASE + timedelta(days=7, hours=12)
    assert selection.validation.start == BASE + timedelta(days=8)
    assert selection.validation.end == current_fold.train.end
    assert selection.test == current_fold.test
    assert selection.fit.end < selection.validation.start
    assert selection.validation.end < selection.test.start
    assert selection.selection_fold_id.startswith("selection_fold_")


def test_selection_split_rejects_spec_that_consumes_fit_window() -> None:
    with pytest.raises(ValueError, match="no positive fit window"):
        split_fold_for_selection(
            fold(),
            spec=SelectionSpec(
                validation_length=timedelta(days=9),
                embargo=timedelta(days=1),
            ),
        )


def test_selection_uses_validation_scores_only_with_deterministic_tie_break() -> None:
    selection = split_fold_for_selection(
        fold(),
        spec=SelectionSpec(validation_length=timedelta(days=2)),
    )
    candidates = (
        score(
            selection_fold_id=selection.selection_fold_id,
            candidate_id="strategy.z",
            result_id="validation-z",
            value="1.25",
        ),
        score(
            selection_fold_id=selection.selection_fold_id,
            candidate_id="strategy.a",
            result_id="validation-a",
            value="1.25",
        ),
        score(
            selection_fold_id=selection.selection_fold_id,
            candidate_id="strategy.b",
            result_id="validation-b",
            value="0.80",
        ),
    )

    maximize = select_validation_candidate(
        selection,
        objective_id="mean_return_v1",
        direction=ObjectiveDirection.MAXIMIZE,
        candidates=candidates,
    )
    minimize_candidates = tuple(
        replace(
            candidate,
            objective_id="drawdown_v1",
            direction=ObjectiveDirection.MINIMIZE,
        )
        for candidate in candidates
    )
    minimize = select_validation_candidate(
        selection,
        objective_id="drawdown_v1",
        direction=ObjectiveDirection.MINIMIZE,
        candidates=minimize_candidates,
    )

    assert maximize.selected_candidate_id == "strategy.a"
    assert minimize.selected_candidate_id == "strategy.b"
    assert maximize.decision_id == select_validation_candidate(
        selection,
        objective_id="mean_return_v1",
        direction=ObjectiveDirection.MAXIMIZE,
        candidates=tuple(reversed(candidates)),
    ).decision_id


def test_selection_rejects_scores_from_another_fold_or_objective() -> None:
    selection = split_fold_for_selection(
        fold(),
        spec=SelectionSpec(validation_length=timedelta(days=2)),
    )
    candidate = score(
        selection_fold_id="selection_fold_other",
        candidate_id="strategy.a",
        result_id="validation-a",
        value="1",
    )

    with pytest.raises(ValueError, match="different selection fold"):
        select_validation_candidate(
            selection,
            objective_id="mean_return_v1",
            direction=ObjectiveDirection.MAXIMIZE,
            candidates=(candidate,),
        )

    current_fold_candidate = replace(candidate, selection_fold_id=selection.selection_fold_id)
    with pytest.raises(ValueError, match="different objective"):
        select_validation_candidate(
            selection,
            objective_id="drawdown_v1",
            direction=ObjectiveDirection.MAXIMIZE,
            candidates=(current_fold_candidate,),
        )

    with pytest.raises(ValueError, match="different objective direction"):
        select_validation_candidate(
            selection,
            objective_id="mean_return_v1",
            direction=ObjectiveDirection.MINIMIZE,
            candidates=(current_fold_candidate,),
        )


def test_selection_rejects_duplicate_or_nonfinite_validation_evidence() -> None:
    selection = split_fold_for_selection(
        fold(),
        spec=SelectionSpec(validation_length=timedelta(days=2)),
    )
    candidate = score(
        selection_fold_id=selection.selection_fold_id,
        candidate_id="strategy.a",
        result_id="validation-a",
        value="1",
    )

    with pytest.raises(ValueError, match="finite"):
        replace(candidate, score=Decimal("NaN"))

    with pytest.raises(ValueError, match="unique candidate_id"):
        select_validation_candidate(
            selection,
            objective_id="mean_return_v1",
            direction=ObjectiveDirection.MAXIMIZE,
            candidates=(candidate, replace(candidate, validation_result_id="validation-b")),
        )

    with pytest.raises(ValueError, match="unique validation_result_id"):
        select_validation_candidate(
            selection,
            objective_id="mean_return_v1",
            direction=ObjectiveDirection.MAXIMIZE,
            candidates=(candidate, replace(candidate, candidate_id="strategy.b")),
        )
