from datetime import timedelta
from decimal import Decimal

import pytest
from test_backtest import BASE, event, risk_engine
from test_research_search import BOUNDARY_ID, FEATURE_IDS, selection_fold, validation_events

from trading_platform.backtest import EventDrivenBacktester
from trading_platform.research_grid import (
    EmaCrossoverParameterGrid,
    EmaCrossoverParameters,
    run_ema_validation_grid_search,
)
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


def test_validation_fixture_still_precedes_test_window() -> None:
    fold = selection_fold()
    assert all(
        item.exchange_timestamp < fold.test.start for item in validation_events()
    )
    assert fold.test.start == BASE
