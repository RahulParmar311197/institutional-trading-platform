from dataclasses import replace
from datetime import timedelta

import pytest
from test_backtest import BASE, event, make_backtester

from trading_platform.research_periods import ResearchWindow, WalkForwardFold
from trading_platform.research_search import run_validation_search
from trading_platform.research_selection import SelectionSpec, split_fold_for_selection
from trading_platform.research_validation import ValidationObjective

BOUNDARY_ID = "research_boundaries_v1_fixture"
FEATURE_IDS = ("market_regime_v1_fixture",)


def selection_fold():
    fold = WalkForwardFold(
        index=0,
        train=ResearchWindow(
            start=BASE - timedelta(minutes=10),
            end=BASE - timedelta(minutes=1),
        ),
        test=ResearchWindow(
            start=BASE,
            end=BASE + timedelta(minutes=5),
        ),
        spec_id="walk_forward_v1_fixture",
    )
    return split_fold_for_selection(
        fold,
        spec=SelectionSpec(validation_length=timedelta(minutes=3)),
    )


def shifted_event(event_id: str, minute: int, price: str):
    timestamp = BASE + timedelta(minutes=minute)
    return replace(
        event(event_id, 0, price),
        exchange_timestamp=timestamp,
        provider_timestamp=timestamp,
        ingestion_timestamp=timestamp,
    )


def validation_events():
    return [
        shifted_event("validation-a", -4, "100"),
        shifted_event("validation-b", -3, "99"),
        shifted_event("validation-c", -2, "101"),
    ]


def test_validation_search_is_order_independent_and_binds_candidate_set() -> None:
    first_candidate = make_backtester(max_order="100000")
    second_candidate = make_backtester(max_order="50000")
    fold = selection_fold()

    first = run_validation_search(
        (first_candidate, second_candidate),
        validation_events(),
        boundary_id=BOUNDARY_ID,
        selection_fold=fold,
        objective=ValidationObjective.TOTAL_RETURN,
        feature_ids=FEATURE_IDS,
    )
    second = run_validation_search(
        (second_candidate, first_candidate),
        list(reversed(validation_events())),
        boundary_id=BOUNDARY_ID,
        selection_fold=fold,
        objective=ValidationObjective.TOTAL_RETURN,
        feature_ids=FEATURE_IDS,
    )

    candidate_ids = tuple(result.candidate.candidate_id for result in first.evaluations)
    assert candidate_ids == tuple(sorted(candidate_ids))
    assert first.candidate_set_id.startswith("validation_candidate_set_v1_")
    assert first.candidate_set_id == second.candidate_set_id
    assert first.decision.decision_id == second.decision.decision_id
    assert first.search_id == second.search_id


def test_validation_search_tie_break_is_deterministic() -> None:
    first_candidate = make_backtester(max_order="100000")
    second_candidate = make_backtester(max_order="50000")
    result = run_validation_search(
        (first_candidate, second_candidate),
        validation_events(),
        boundary_id=BOUNDARY_ID,
        selection_fold=selection_fold(),
        objective=ValidationObjective.TOTAL_RETURN,
        feature_ids=FEATURE_IDS,
    )

    candidate_ids = tuple(item.candidate.candidate_id for item in result.evaluations)
    assert result.decision.selected_candidate_id == min(candidate_ids)


def test_validation_search_rejects_duplicate_candidate_identity() -> None:
    candidate = make_backtester()

    with pytest.raises(ValueError, match="unique candidate identities"):
        run_validation_search(
            (candidate, make_backtester()),
            validation_events(),
            boundary_id=BOUNDARY_ID,
            selection_fold=selection_fold(),
            objective=ValidationObjective.TOTAL_RETURN,
            feature_ids=FEATURE_IDS,
        )


def test_validation_search_rejects_test_fold_event_before_selection() -> None:
    with pytest.raises(ValueError, match="validation window"):
        run_validation_search(
            (make_backtester(),),
            [shifted_event("test-leak", 0, "100")],
            boundary_id=BOUNDARY_ID,
            selection_fold=selection_fold(),
            objective=ValidationObjective.TOTAL_RETURN,
            feature_ids=FEATURE_IDS,
        )


def test_validation_search_rejects_empty_candidate_set() -> None:
    with pytest.raises(ValueError, match="at least one backtester"):
        run_validation_search(
            (),
            validation_events(),
            boundary_id=BOUNDARY_ID,
            selection_fold=selection_fold(),
            objective=ValidationObjective.MAX_DRAWDOWN_PCT,
        )
