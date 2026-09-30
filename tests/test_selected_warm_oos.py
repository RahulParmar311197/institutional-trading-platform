from dataclasses import replace
from datetime import timedelta

import pytest
from test_backtest import BASE, event, make_backtester

from trading_platform.research_periods import ResearchWindow, WalkForwardFold
from trading_platform.research_selection import (
    SelectionSpec,
    select_validation_candidate,
    split_fold_for_selection,
)
from trading_platform.research_validation import (
    ValidationObjective,
    evaluate_fixed_strategy_validation_fold,
    score_validation_result,
)
from trading_platform.research_warm_state import prepare_pipeline_warm_state
from trading_platform.walk_forward import evaluate_selected_warm_strategy_oos_fold

BOUNDARY_ID = "research_boundaries_v1_fixture"
FEATURE_IDS = ("market_regime_v1_fixture",)


def fold() -> WalkForwardFold:
    return WalkForwardFold(
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


def shifted_event(event_id: str, minute: int, price: str):
    timestamp = BASE + timedelta(minutes=minute)
    return replace(
        event(event_id, 0, price),
        exchange_timestamp=timestamp,
        provider_timestamp=timestamp,
        ingestion_timestamp=timestamp,
    )


def selected_inputs():
    current_fold = fold()
    selection = split_fold_for_selection(
        current_fold,
        spec=SelectionSpec(validation_length=timedelta(minutes=3)),
    )
    backtester = make_backtester()
    validation = evaluate_fixed_strategy_validation_fold(
        backtester,
        [
            shifted_event("validation-a", -4, "100"),
            shifted_event("validation-b", -3, "99"),
            shifted_event("validation-c", -2, "101"),
        ],
        boundary_id=BOUNDARY_ID,
        selection_fold=selection,
        feature_ids=FEATURE_IDS,
    )
    score = score_validation_result(
        validation,
        objective=ValidationObjective.TOTAL_RETURN,
    )
    decision = select_validation_candidate(
        selection,
        objective_id=score.objective_id,
        direction=score.direction,
        candidates=(score,),
    )
    prepared = prepare_pipeline_warm_state(
        backtester,
        [
            shifted_event("warm-a", -4, "100"),
            shifted_event("warm-b", -3, "99"),
            shifted_event("warm-c", -2, "101"),
        ],
        boundary_id=BOUNDARY_ID,
        fold=current_fold,
        source_window=current_fold.train,
        feature_ids=FEATURE_IDS,
    )
    return current_fold, selection, backtester, decision, prepared


def test_selected_warm_oos_binds_selection_and_preparation_before_test() -> None:
    current_fold, selection, backtester, decision, prepared = selected_inputs()
    result = evaluate_selected_warm_strategy_oos_fold(
        backtester,
        [
            shifted_event("test-a", 0, "102"),
            shifted_event("test-b", 1, "102"),
        ],
        boundary_id=BOUNDARY_ID,
        fold=current_fold,
        selection_fold=selection,
        decision=decision,
        prepared_state=prepared,
        feature_ids=FEATURE_IDS,
    )

    assert result.selection_decision_id == decision.decision_id
    assert result.candidate_id == decision.selected_candidate_id
    assert result.preparation_state_id == prepared.preparation_state_id
    assert result.oos.provenance.fold_id == current_fold.fold_id
    assert result.result_id.startswith("selected_warm_oos_v1_")


def test_selected_warm_oos_rejects_candidate_mismatch_before_test() -> None:
    current_fold, selection, backtester, decision, prepared = selected_inputs()

    with pytest.raises(ValueError, match="selected validation candidate"):
        evaluate_selected_warm_strategy_oos_fold(
            backtester,
            [shifted_event("test", 0, "102")],
            boundary_id=BOUNDARY_ID,
            fold=current_fold,
            selection_fold=selection,
            decision=decision,
            prepared_state=prepared,
            feature_ids=("different-feature",),
        )


def test_selected_warm_oos_rejects_test_window_leakage() -> None:
    current_fold, selection, backtester, decision, prepared = selected_inputs()

    with pytest.raises(ValueError, match="test window"):
        evaluate_selected_warm_strategy_oos_fold(
            backtester,
            [shifted_event("train-leak", -2, "102")],
            boundary_id=BOUNDARY_ID,
            fold=current_fold,
            selection_fold=selection,
            decision=decision,
            prepared_state=prepared,
            feature_ids=FEATURE_IDS,
        )
