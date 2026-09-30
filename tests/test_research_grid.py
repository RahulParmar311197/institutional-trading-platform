from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest
from test_backtest import BASE, event, risk_engine
from test_research_search import BOUNDARY_ID, FEATURE_IDS, selection_fold, validation_events

from trading_platform.backtest import EventDrivenBacktester
from trading_platform.research_grid import (
    EmaCrossoverParameterGrid,
    EmaCrossoverParameters,
    FoldValidationInput,
    run_ema_validation_grid_search,
    run_ema_walk_forward_grid_search,
)
from trading_platform.research_periods import ResearchWindow, WalkForwardFold
from trading_platform.research_selection import SelectionSpec
from trading_platform.research_validation import ValidationObjective
from trading_platform.strategy import EmaCrossoverStrategy


def make_candidate(parameters: EmaCrossoverParameters) -> EventDrivenBacktester:
    return EventDrivenBacktester(
        interval=timedelta(minutes=1),
        strategy=EmaCrossoverStrategy(
            fast_period=parameters.fast_period,
            slow_period=parameters.slow_period,
        ),
        risk_engine=risk_engine(),
        requested_quantity=1,
        starting_equity=Decimal("10000"),
    )


def parent_fold(index: int, offset: int) -> WalkForwardFold:
    return WalkForwardFold(
        index=index,
        train=ResearchWindow(
            start=BASE + timedelta(minutes=offset - 10),
            end=BASE + timedelta(minutes=offset - 1),
        ),
        test=ResearchWindow(
            start=BASE + timedelta(minutes=offset),
            end=BASE + timedelta(minutes=offset + 5),
        ),
        spec_id="walk_forward_v1_fixture",
    )


def validation_event(event_id: str, minute: int, price: str):
    timestamp = BASE + timedelta(minutes=minute)
    return replace(
        event(event_id, max(0, minute), price),
        exchange_timestamp=timestamp,
        provider_timestamp=timestamp,
        ingestion_timestamp=timestamp,
    )


def test_parameter_grid_from_axes_is_deterministic_and_cartesian() -> None:
    first = EmaCrossoverParameterGrid.from_axes(
        fast_periods=(2, 1),
        slow_periods=(4, 3),
    )
    second = EmaCrossoverParameterGrid.from_axes(
        fast_periods=(1, 2),
        slow_periods=(3, 4),
    )

    assert first.candidates == (
        EmaCrossoverParameters(1, 3),
        EmaCrossoverParameters(1, 4),
        EmaCrossoverParameters(2, 3),
        EmaCrossoverParameters(2, 4),
    )
    assert first.candidates == second.candidates
    assert first.grid_id == second.grid_id


def test_parameter_grid_rejects_invalid_or_duplicate_axes() -> None:
    with pytest.raises(ValueError, match="duplicates"):
        EmaCrossoverParameterGrid.from_axes(
            fast_periods=(1, 1),
            slow_periods=(3,),
        )
    with pytest.raises(ValueError, match="fast_period < slow_period"):
        EmaCrossoverParameterGrid.from_axes(
            fast_periods=(3,),
            slow_periods=(2,),
        )
    with pytest.raises(ValueError, match="positive integers"):
        EmaCrossoverParameterGrid.from_axes(
            fast_periods=(True,),
            slow_periods=(3,),
        )


def test_parameter_grid_rejects_noncanonical_manual_candidate_order() -> None:
    with pytest.raises(ValueError, match="canonically ordered"):
        EmaCrossoverParameterGrid(
            candidates=(
                EmaCrossoverParameters(2, 4),
                EmaCrossoverParameters(1, 3),
            )
        )


def test_grid_search_binds_declared_grid_to_validation_search() -> None:
    grid = EmaCrossoverParameterGrid.from_axes(
        fast_periods=(1,),
        slow_periods=(2, 3),
    )
    result = run_ema_validation_grid_search(
        grid,
        make_candidate,
        validation_events(),
        boundary_id=BOUNDARY_ID,
        selection_fold=selection_fold(),
        objective=ValidationObjective.TOTAL_RETURN,
        feature_ids=FEATURE_IDS,
    )

    strategy_ids = tuple(
        item.candidate.strategy_id for item in result.search.evaluations
    )
    assert set(strategy_ids) == {candidate.parameter_id for candidate in grid.candidates}
    assert result.grid_id == grid.grid_id
    assert result.result_id.startswith("ema_grid_search_v1_")


def test_grid_search_rejects_factory_candidate_mismatch() -> None:
    grid = EmaCrossoverParameterGrid.from_axes(
        fast_periods=(1,),
        slow_periods=(2,),
    )

    def mismatched_factory(parameters: EmaCrossoverParameters) -> EventDrivenBacktester:
        del parameters
        return EventDrivenBacktester(
            interval=timedelta(minutes=1),
            strategy=EmaCrossoverStrategy(fast_period=1, slow_period=3),
            risk_engine=risk_engine(),
            requested_quantity=1,
            starting_equity=Decimal("10000"),
        )

    with pytest.raises(ValueError, match="does not match declared EMA grid candidate"):
        run_ema_validation_grid_search(
            grid,
            mismatched_factory,
            validation_events(),
            boundary_id=BOUNDARY_ID,
            selection_fold=selection_fold(),
            objective=ValidationObjective.TOTAL_RETURN,
        )


def test_grid_search_rejects_test_window_evidence() -> None:
    grid = EmaCrossoverParameterGrid.from_axes(
        fast_periods=(1,),
        slow_periods=(2,),
    )

    with pytest.raises(ValueError, match="validation window"):
        run_ema_validation_grid_search(
            grid,
            make_candidate,
            [event("test-leak", 0, "100")],
            boundary_id=BOUNDARY_ID,
            selection_fold=selection_fold(),
            objective=ValidationObjective.TOTAL_RETURN,
        )


def test_grid_search_identity_changes_when_grid_changes() -> None:
    first = EmaCrossoverParameterGrid.from_axes(
        fast_periods=(1,),
        slow_periods=(2,),
    )
    second = EmaCrossoverParameterGrid.from_axes(
        fast_periods=(1,),
        slow_periods=(2, 3),
    )

    assert first.grid_id != second.grid_id


def test_walk_forward_grid_search_reuses_exact_grid_across_folds() -> None:
    grid = EmaCrossoverParameterGrid.from_axes(
        fast_periods=(1,),
        slow_periods=(2, 3),
    )
    selection_spec = SelectionSpec(validation_length=timedelta(minutes=3))
    fold_inputs = (
        FoldValidationInput(fold=parent_fold(0, 0), events=tuple(validation_events())),
        FoldValidationInput(
            fold=parent_fold(1, 10),
            events=(
                validation_event("fold-1-a", 6, "101"),
                validation_event("fold-1-b", 7, "100"),
                validation_event("fold-1-c", 8, "102"),
            ),
        ),
    )

    first = run_ema_walk_forward_grid_search(
        grid,
        make_candidate,
        fold_inputs,
        boundary_id=BOUNDARY_ID,
        selection_spec=selection_spec,
        objective=ValidationObjective.TOTAL_RETURN,
        feature_ids=FEATURE_IDS,
    )
    second = run_ema_walk_forward_grid_search(
        grid,
        make_candidate,
        fold_inputs,
        boundary_id=BOUNDARY_ID,
        selection_spec=selection_spec,
        objective=ValidationObjective.TOTAL_RETURN,
        feature_ids=FEATURE_IDS,
    )

    assert len(first.folds) == 2
    assert all(result.grid_id == grid.grid_id for result in first.folds)
    assert all(
        len(result.search.evaluations) == len(grid.candidates) for result in first.folds
    )
    assert first.result_id == second.result_id
    assert first.result_id.startswith("ema_walk_forward_grid_search_v1_")


def test_walk_forward_grid_search_rejects_out_of_order_folds() -> None:
    grid = EmaCrossoverParameterGrid.from_axes(
        fast_periods=(1,),
        slow_periods=(2,),
    )
    first = FoldValidationInput(
        fold=parent_fold(0, 0),
        events=tuple(validation_events()),
    )
    second = FoldValidationInput(
        fold=parent_fold(1, 10),
        events=(
            validation_event("fold-1-a", 6, "101"),
            validation_event("fold-1-b", 7, "100"),
            validation_event("fold-1-c", 8, "102"),
        ),
    )

    with pytest.raises(ValueError, match="unique increasing indices"):
        run_ema_walk_forward_grid_search(
            grid,
            make_candidate,
            (second, first),
            boundary_id=BOUNDARY_ID,
            selection_spec=SelectionSpec(validation_length=timedelta(minutes=3)),
            objective=ValidationObjective.TOTAL_RETURN,
        )


def test_walk_forward_grid_search_rejects_test_event_in_any_fold() -> None:
    grid = EmaCrossoverParameterGrid.from_axes(
        fast_periods=(1,),
        slow_periods=(2,),
    )
    contaminated = FoldValidationInput(
        fold=parent_fold(1, 10),
        events=(validation_event("test-leak", 10, "100"),),
    )

    with pytest.raises(ValueError, match="validation window"):
        run_ema_walk_forward_grid_search(
            grid,
            make_candidate,
            (contaminated,),
            boundary_id=BOUNDARY_ID,
            selection_spec=SelectionSpec(validation_length=timedelta(minutes=3)),
            objective=ValidationObjective.TOTAL_RETURN,
        )


def test_validation_fixture_still_precedes_test_window() -> None:
    fold = selection_fold()
    assert all(
        item.exchange_timestamp < fold.test.start for item in validation_events()
    )
    assert fold.test.start == BASE
