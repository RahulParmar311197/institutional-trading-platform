from datetime import timedelta

import pytest
from test_research_grid import make_candidate, parent_fold, validation_event
from test_research_search import BOUNDARY_ID, FEATURE_IDS

from trading_platform.research_grid import (
    EmaCrossoverParameterGrid,
    EmaCrossoverParameters,
    evaluate_ema_grid_selected_warm_oos_fold,
    run_ema_validation_grid_search,
)
from trading_platform.research_grid_reporting import (
    EmaGridOOSFoldResult,
    build_ema_grid_oos_report,
)
from trading_platform.research_selection import SelectionSpec, split_fold_for_selection
from trading_platform.research_validation import ValidationObjective
from trading_platform.research_warm_state import prepare_pipeline_warm_state

SELECTION_SPEC = SelectionSpec(validation_length=timedelta(minutes=3))
GRID = EmaCrossoverParameterGrid.from_axes(fast_periods=(1,), slow_periods=(2,))


def evaluated_fold(index: int, offset: int):
    current_fold = parent_fold(index, offset)
    selection = split_fold_for_selection(current_fold, spec=SELECTION_SPEC)
    validation = [
        validation_event(f"validation-{index}-a", offset - 4, "100"),
        validation_event(f"validation-{index}-b", offset - 3, "99"),
        validation_event(f"validation-{index}-c", offset - 2, "101"),
    ]
    search = run_ema_validation_grid_search(
        GRID,
        make_candidate,
        validation,
        boundary_id=BOUNDARY_ID,
        selection_fold=selection,
        objective=ValidationObjective.TOTAL_RETURN,
        feature_ids=FEATURE_IDS,
    )
    backtester = make_candidate(EmaCrossoverParameters(1, 2))
    prepared = prepare_pipeline_warm_state(
        backtester,
        [
            validation_event(f"warm-{index}-a", offset - 4, "100"),
            validation_event(f"warm-{index}-b", offset - 3, "99"),
            validation_event(f"warm-{index}-c", offset - 2, "101"),
        ],
        boundary_id=BOUNDARY_ID,
        fold=current_fold,
        source_window=current_fold.train,
        feature_ids=FEATURE_IDS,
    )
    result = evaluate_ema_grid_selected_warm_oos_fold(
        search,
        backtester,
        [
            validation_event(f"test-{index}-a", offset, "102"),
            validation_event(f"test-{index}-b", offset + 1, "102"),
        ],
        boundary_id=BOUNDARY_ID,
        fold=current_fold,
        selection_fold=selection,
        prepared_state=prepared,
        feature_ids=FEATURE_IDS,
    )
    return EmaGridOOSFoldResult(fold=current_fold, result=result)


def test_grid_oos_report_preserves_per_fold_research_identities() -> None:
    first = evaluated_fold(0, 0)
    second = evaluated_fold(1, 10)

    report = build_ema_grid_oos_report((first, second))

    assert report.grid_id == GRID.grid_id
    assert len(report.folds) == 2
    assert [item.search_id for item in report.folds] == [
        first.result.search_id,
        second.result.search_id,
    ]
    assert [item.selection_decision_id for item in report.folds] == [
        first.result.selected_warm.selection_decision_id,
        second.result.selected_warm.selection_decision_id,
    ]
    assert [item.preparation_state_id for item in report.folds] == [
        first.result.selected_warm.preparation_state_id,
        second.result.selected_warm.preparation_state_id,
    ]
    assert report.mean_fold_total_return == sum(
        (item.total_return for item in report.folds),
        start=report.folds[0].total_return * 0,
    ) / len(report.folds)
    assert report.report_id.startswith("ema_grid_oos_report_v1_")


def test_grid_oos_report_is_deterministic() -> None:
    evaluations = (evaluated_fold(0, 0), evaluated_fold(1, 10))

    first = build_ema_grid_oos_report(evaluations)
    second = build_ema_grid_oos_report(evaluations)

    assert first == second
    assert first.report_id == second.report_id


def test_grid_oos_report_rejects_out_of_order_or_missing_fold() -> None:
    first = evaluated_fold(0, 0)
    second = evaluated_fold(1, 10)

    with pytest.raises(ValueError, match="ordered and contiguous"):
        build_ema_grid_oos_report((second, first))
    with pytest.raises(ValueError, match="ordered and contiguous"):
        build_ema_grid_oos_report((second,))


def test_grid_oos_report_does_not_require_same_selected_strategy_across_folds() -> None:
    first = evaluated_fold(0, 0)
    second = evaluated_fold(1, 10)
    report = build_ema_grid_oos_report((first, second))

    assert all(item.grid_id == GRID.grid_id for item in report.folds)
    assert not hasattr(report, "strategy_id")
    assert not hasattr(report, "backtest_config_digest")
