import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass

from trading_platform.backtest import EventDrivenBacktester
from trading_platform.recorded_events import RecordedMarketEvent
from trading_platform.research_periods import WalkForwardFold
from trading_platform.research_search import ValidationSearchResult, run_validation_search
from trading_platform.research_selection import (
    SelectionFold,
    SelectionSpec,
    split_fold_for_selection,
)
from trading_platform.research_validation import ValidationObjective

EMA_PARAMETER_GRID_VERSION = 1


@dataclass(frozen=True, order=True, slots=True)
class EmaCrossoverParameters:
    fast_period: int
    slow_period: int

    def __post_init__(self) -> None:
        if self.fast_period <= 0 or self.slow_period <= 0:
            raise ValueError("EMA periods must be positive")
        if self.fast_period >= self.slow_period:
            raise ValueError("EMA grid requires fast_period < slow_period")

    @property
    def parameter_id(self) -> str:
        return f"ema_crossover_v1_{self.fast_period}_{self.slow_period}"


@dataclass(frozen=True, slots=True)
class EmaCrossoverParameterGrid:
    candidates: tuple[EmaCrossoverParameters, ...]
    version: int = EMA_PARAMETER_GRID_VERSION

    def __post_init__(self) -> None:
        if self.version != EMA_PARAMETER_GRID_VERSION:
            raise ValueError("unsupported EMA parameter-grid version")
        if not self.candidates:
            raise ValueError("EMA parameter grid requires at least one candidate")
        if len(set(self.candidates)) != len(self.candidates):
            raise ValueError("EMA parameter grid must not contain duplicate candidates")
        if self.candidates != tuple(sorted(self.candidates)):
            raise ValueError("EMA parameter-grid candidates must be canonically ordered")

    @classmethod
    def from_axes(
        cls,
        *,
        fast_periods: tuple[int, ...],
        slow_periods: tuple[int, ...],
    ) -> "EmaCrossoverParameterGrid":
        if not fast_periods or not slow_periods:
            raise ValueError("EMA parameter-grid axes must not be empty")
        if len(set(fast_periods)) != len(fast_periods):
            raise ValueError("fast_periods must not contain duplicates")
        if len(set(slow_periods)) != len(slow_periods):
            raise ValueError("slow_periods must not contain duplicates")
        if any(type(period) is not int or period <= 0 for period in fast_periods):
            raise ValueError("fast_periods must contain positive integers")
        if any(type(period) is not int or period <= 0 for period in slow_periods):
            raise ValueError("slow_periods must contain positive integers")

        pairs = tuple(
            sorted(
                EmaCrossoverParameters(fast_period=fast, slow_period=slow)
                for fast in fast_periods
                for slow in slow_periods
            )
        )
        return cls(candidates=pairs)

    @property
    def grid_id(self) -> str:
        payload = {
            "version": self.version,
            "candidates": [
                {
                    "fast_period": candidate.fast_period,
                    "slow_period": candidate.slow_period,
                }
                for candidate in self.candidates
            ],
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        return f"ema_parameter_grid_v{self.version}_{hashlib.sha256(encoded).hexdigest()}"


@dataclass(frozen=True, slots=True)
class EmaGridSearchResult:
    grid_id: str
    search: ValidationSearchResult

    def __post_init__(self) -> None:
        if not self.grid_id.strip():
            raise ValueError("grid_id must not be empty")

    @property
    def result_id(self) -> str:
        payload = {
            "grid_id": self.grid_id,
            "search_id": self.search.search_id,
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        return f"ema_grid_search_v1_{hashlib.sha256(encoded).hexdigest()}"


@dataclass(frozen=True, slots=True)
class FoldValidationInput:
    fold: WalkForwardFold
    events: tuple[RecordedMarketEvent, ...]

    def __post_init__(self) -> None:
        if not self.events:
            raise ValueError("fold validation input requires events")


@dataclass(frozen=True, slots=True)
class EmaWalkForwardGridSearchResult:
    grid_id: str
    selection_spec_id: str
    objective: ValidationObjective
    folds: tuple[EmaGridSearchResult, ...]

    def __post_init__(self) -> None:
        if not self.grid_id.strip():
            raise ValueError("grid_id must not be empty")
        if not self.selection_spec_id.strip():
            raise ValueError("selection_spec_id must not be empty")
        if not self.folds:
            raise ValueError("walk-forward grid search requires fold results")
        if any(result.grid_id != self.grid_id for result in self.folds):
            raise ValueError("walk-forward grid search contains a different grid")
        if any(result.search.objective is not self.objective for result in self.folds):
            raise ValueError("walk-forward grid search contains a different objective")
        selection_fold_ids = tuple(result.search.selection_fold_id for result in self.folds)
        if len(set(selection_fold_ids)) != len(selection_fold_ids):
            raise ValueError("walk-forward grid search contains duplicate selection folds")

    @property
    def result_id(self) -> str:
        payload = {
            "grid_id": self.grid_id,
            "selection_spec_id": self.selection_spec_id,
            "objective_id": self.objective.value,
            "fold_result_ids": [result.result_id for result in self.folds],
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        return f"ema_walk_forward_grid_search_v1_{hashlib.sha256(encoded).hexdigest()}"


def run_ema_validation_grid_search(
    grid: EmaCrossoverParameterGrid,
    backtester_factory: Callable[[EmaCrossoverParameters], EventDrivenBacktester],
    events: list[RecordedMarketEvent],
    *,
    boundary_id: str,
    selection_fold: SelectionFold,
    objective: ValidationObjective,
    feature_ids: tuple[str, ...] = (),
) -> EmaGridSearchResult:
    backtesters: list[EventDrivenBacktester] = []
    for parameters in grid.candidates:
        backtester = backtester_factory(parameters)
        expected_strategy_id = parameters.parameter_id
        if backtester.strategy.strategy_id != expected_strategy_id:
            raise ValueError(
                "backtester factory strategy does not match declared EMA grid candidate"
            )
        backtesters.append(backtester)

    search = run_validation_search(
        tuple(backtesters),
        events,
        boundary_id=boundary_id,
        selection_fold=selection_fold,
        objective=objective,
        feature_ids=feature_ids,
    )
    return EmaGridSearchResult(grid_id=grid.grid_id, search=search)


def run_ema_walk_forward_grid_search(
    grid: EmaCrossoverParameterGrid,
    backtester_factory: Callable[[EmaCrossoverParameters], EventDrivenBacktester],
    fold_inputs: tuple[FoldValidationInput, ...],
    *,
    boundary_id: str,
    selection_spec: SelectionSpec,
    objective: ValidationObjective,
    feature_ids: tuple[str, ...] = (),
) -> EmaWalkForwardGridSearchResult:
    if not fold_inputs:
        raise ValueError("walk-forward grid search requires fold inputs")
    indices = tuple(item.fold.index for item in fold_inputs)
    if indices != tuple(sorted(indices)) or len(set(indices)) != len(indices):
        raise ValueError("walk-forward fold inputs must have unique increasing indices")
    spec_ids = {item.fold.spec_id for item in fold_inputs}
    if len(spec_ids) != 1:
        raise ValueError("walk-forward fold inputs must share one fold specification")

    results: list[EmaGridSearchResult] = []
    for item in fold_inputs:
        selection_fold = split_fold_for_selection(item.fold, spec=selection_spec)
        results.append(
            run_ema_validation_grid_search(
                grid,
                backtester_factory,
                list(item.events),
                boundary_id=boundary_id,
                selection_fold=selection_fold,
                objective=objective,
                feature_ids=feature_ids,
            )
        )

    return EmaWalkForwardGridSearchResult(
        grid_id=grid.grid_id,
        selection_spec_id=selection_spec.spec_id,
        objective=objective,
        folds=tuple(results),
    )
