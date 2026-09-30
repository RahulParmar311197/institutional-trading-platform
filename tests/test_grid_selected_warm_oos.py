from datetime import timedelta

import pytest
from test_research_grid import make_candidate
from test_selected_warm_oos import BOUNDARY_ID, FEATURE_IDS, fold, shifted_event

from trading_platform.research_grid import (
    EmaCrossoverParameterGrid,
    EmaCrossoverParameters,
    evaluate_ema_grid_selected_warm_oos_fold,
    run_ema_validation_grid_search,
)
from trading_platform.research_selection import SelectionSpec, split_fold_for_selection
from trading_platform.research_validation import ValidationObjective
from trading_platform.research_warm_state import prepare_pipeline_warm_state


def inputs():
    current_fold = fold()
    selection = split_fold_for_selection(
        current_fold,
        spec=SelectionSpec(validation_length=timedelta(minutes=3)),
    )
    grid = EmaCrossoverParameterGrid.from_axes(
        fast_periods=(1,),
        slow_periods=(2,),
    )
    grid_search = run_ema_validation_grid_search(
        grid,
        make_candidate,
        [
            shifted_event("validation-a", -4, "100"),
            shifted_event("validation-b", -3, "99"),
            shifted_event("validation-c", -2, "101"),
        ],
        boundary_id=BOUNDARY_ID,
        selection_fold=selection,
        objective=ValidationObjective.TOTAL_RETURN,
        feature_ids=FEATURE_IDS,
    )
    backtester = make_candidate(EmaCrossoverParameters(1, 2))
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
    return current_fold, selection, grid_search, backtester, prepared


def test_grid_selected_warm_oos_binds_search_and_execution_evidence() -> None:
    current_fold, selection, grid_search, backtester, prepared = inputs()

    result = evaluate_ema_grid_selected_warm_oos_fold(
        grid_search,
        backtester,
        [
            shifted_event("test-a", 0, "102"),
            shifted_event("test-b", 1, "102"),
        ],
        boundary_id=BOUNDARY_ID,
        fold=current_fold,
        selection_fold=selection,
        prepared_state=prepared,
        feature_ids=FEATURE_IDS,
    )

    assert result.grid_id == grid_search.grid_id
    assert result.search_id == grid_search.search.search_id
    assert (
        result.selected_warm.selection_decision_id
        == grid_search.search.decision.decision_id
    )
    assert result.selected_warm.preparation_state_id == prepared.preparation_state_id
    assert result.result_id.startswith("ema_grid_selected_warm_oos_v1_")


def test_grid_selected_warm_oos_rejects_different_selection_fold() -> None:
    current_fold, _, grid_search, backtester, prepared = inputs()
    different_selection = split_fold_for_selection(
        current_fold,
        spec=SelectionSpec(validation_length=timedelta(minutes=2)),
    )

    with pytest.raises(ValueError, match="grid search does not belong"):
        evaluate_ema_grid_selected_warm_oos_fold(
            grid_search,
            backtester,
            [shifted_event("test", 0, "102")],
            boundary_id=BOUNDARY_ID,
            fold=current_fold,
            selection_fold=different_selection,
            prepared_state=prepared,
            feature_ids=FEATURE_IDS,
        )


def test_grid_selected_warm_oos_rejects_unselected_candidate() -> None:
    current_fold, selection, grid_search, _, prepared = inputs()
    wrong_backtester = make_candidate(EmaCrossoverParameters(1, 3))

    with pytest.raises(ValueError, match="selected validation candidate"):
        evaluate_ema_grid_selected_warm_oos_fold(
            grid_search,
            wrong_backtester,
            [shifted_event("test", 0, "102")],
            boundary_id=BOUNDARY_ID,
            fold=current_fold,
            selection_fold=selection,
            prepared_state=prepared,
            feature_ids=FEATURE_IDS,
        )
