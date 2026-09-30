from dataclasses import replace
from datetime import timedelta

import pytest
from test_backtest import BASE, event, make_backtester, sample_events

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
from trading_platform.walk_forward import (
    evaluate_fixed_strategy_oos_fold,
    evaluate_selected_strategy_oos_fold,
    evaluate_warm_strategy_oos_fold,
)

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


def shifted_event(event_id: str, minute: int):
    timestamp = BASE + timedelta(minutes=minute)
    return replace(
        event(event_id, 0, "100"),
        exchange_timestamp=timestamp,
        provider_timestamp=timestamp,
        ingestion_timestamp=timestamp,
    )


def priced_shifted_event(event_id: str, minute: int, price: str):
    timestamp = BASE + timedelta(minutes=minute)
    return replace(
        event(event_id, 0, price),
        exchange_timestamp=timestamp,
        provider_timestamp=timestamp,
        ingestion_timestamp=timestamp,
    )


def test_fixed_strategy_oos_fold_matches_direct_cold_start_backtest() -> None:
    events = sample_events()
    backtester = make_backtester()

    envelope = evaluate_fixed_strategy_oos_fold(
        backtester,
        events,
        boundary_id=BOUNDARY_ID,
        fold=fold(),
        feature_ids=FEATURE_IDS,
    )

    assert envelope.result == backtester.run(events)
    assert envelope.provenance.boundary_id == BOUNDARY_ID
    assert envelope.provenance.fold_id == fold().fold_id
    assert envelope.provenance.fold_spec_id == fold().spec_id
    assert envelope.provenance.strategy_id == backtester.strategy.strategy_id
    assert envelope.provenance.feature_ids == FEATURE_IDS


def test_fixed_strategy_oos_fold_is_deterministic_for_unordered_input() -> None:
    events = sample_events()
    backtester = make_backtester()

    first = evaluate_fixed_strategy_oos_fold(
        backtester,
        events,
        boundary_id=BOUNDARY_ID,
        fold=fold(),
        feature_ids=FEATURE_IDS,
    )
    second = evaluate_fixed_strategy_oos_fold(
        backtester,
        list(reversed(events)),
        boundary_id=BOUNDARY_ID,
        fold=fold(),
        feature_ids=FEATURE_IDS,
    )

    assert first.provenance.provenance_id == second.provenance.provenance_id
    assert first.result_id == second.result_id


def test_fixed_strategy_oos_fold_rejects_training_window_event() -> None:
    timestamp = BASE - timedelta(minutes=2)
    leaked = replace(
        event("train-leak", 0, "100"),
        exchange_timestamp=timestamp,
        provider_timestamp=timestamp,
        ingestion_timestamp=timestamp,
    )

    with pytest.raises(ValueError, match="confined to the fold test window"):
        evaluate_fixed_strategy_oos_fold(
            make_backtester(),
            [leaked, *sample_events()],
            boundary_id=BOUNDARY_ID,
            fold=fold(),
        )


def test_fixed_strategy_oos_fold_rejects_event_at_half_open_test_end() -> None:
    end_event = event("test-end", 5, "100")

    with pytest.raises(ValueError, match="confined to the fold test window"):
        evaluate_fixed_strategy_oos_fold(
            make_backtester(),
            [*sample_events(), end_event],
            boundary_id=BOUNDARY_ID,
            fold=fold(),
        )


def test_fixed_strategy_oos_fold_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="at least one recorded event"):
        evaluate_fixed_strategy_oos_fold(
            make_backtester(),
            [],
            boundary_id=BOUNDARY_ID,
            fold=fold(),
        )


def test_warm_oos_uses_only_closed_training_history() -> None:
    current_fold = fold()
    backtester = make_backtester()
    prepared = prepare_pipeline_warm_state(
        backtester,
        [
            priced_shifted_event("warm-a", -4, "100"),
            priced_shifted_event("warm-b", -3, "99"),
            priced_shifted_event("warm-pending", -2, "50"),
        ],
        boundary_id=BOUNDARY_ID,
        fold=current_fold,
        source_window=current_fold.train,
        feature_ids=FEATURE_IDS,
    )
    test_events = [
        priced_shifted_event("test-a", 0, "101"),
        priced_shifted_event("test-b", 1, "101"),
    ]

    cold = evaluate_fixed_strategy_oos_fold(
        make_backtester(),
        test_events,
        boundary_id=BOUNDARY_ID,
        fold=current_fold,
        feature_ids=FEATURE_IDS,
    )
    warm = evaluate_warm_strategy_oos_fold(
        backtester,
        test_events,
        boundary_id=BOUNDARY_ID,
        fold=current_fold,
        prepared_state=prepared,
        feature_ids=FEATURE_IDS,
    )

    expected_warm_close = priced_shifted_event("expected", -3, "99").price
    assert cold.result.metrics.trade_count == 0
    assert warm.oos.result.metrics.trade_count == 1
    assert warm.oos.result.trades[0].reference_price == test_events[0].price
    assert all(candle.end <= current_fold.train.end for candle in prepared.state.closed_candles)
    assert prepared.state.closed_candles[-1].close == expected_warm_close
    assert warm.preparation_state_id == prepared.preparation_state_id
    assert warm.result_id.startswith("warm_oos_v1_")


def test_warm_oos_rejects_mismatched_provenance() -> None:
    current_fold = fold()
    backtester = make_backtester()
    prepared = prepare_pipeline_warm_state(
        backtester,
        [
            priced_shifted_event("warm-a", -4, "100"),
            priced_shifted_event("warm-b", -3, "99"),
        ],
        boundary_id=BOUNDARY_ID,
        fold=current_fold,
        source_window=current_fold.train,
        feature_ids=FEATURE_IDS,
    )

    with pytest.raises(ValueError, match="features"):
        evaluate_warm_strategy_oos_fold(
            backtester,
            [
                priced_shifted_event("test-a", 0, "101"),
                priced_shifted_event("test-b", 1, "101"),
            ],
            boundary_id=BOUNDARY_ID,
            fold=current_fold,
            prepared_state=prepared,
            feature_ids=("different-feature",),
        )


def test_validation_selection_is_bound_before_oos_test_evaluation() -> None:
    current_fold = fold()
    selection = split_fold_for_selection(
        current_fold,
        spec=SelectionSpec(validation_length=timedelta(minutes=3)),
    )
    backtester = make_backtester()
    validation = evaluate_fixed_strategy_validation_fold(
        backtester,
        [
            shifted_event("validation-a", -4),
            shifted_event("validation-b", -3),
            shifted_event("validation-c", -2),
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

    selected = evaluate_selected_strategy_oos_fold(
        backtester,
        sample_events(),
        boundary_id=BOUNDARY_ID,
        fold=current_fold,
        selection_fold=selection,
        decision=decision,
        feature_ids=FEATURE_IDS,
    )

    assert selected.selection_decision_id == decision.decision_id
    assert selected.candidate_id == decision.selected_candidate_id
    assert selected.oos.provenance.fold_id == current_fold.fold_id
    assert selected.result_id.startswith("selected_oos_v1_")


def test_selected_oos_rejects_unselected_candidate_configuration() -> None:
    current_fold = fold()
    selection = split_fold_for_selection(
        current_fold,
        spec=SelectionSpec(validation_length=timedelta(minutes=3)),
    )
    backtester = make_backtester()
    validation = evaluate_fixed_strategy_validation_fold(
        backtester,
        [shifted_event("validation", -2)],
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

    with pytest.raises(ValueError, match="does not match selected validation candidate"):
        evaluate_selected_strategy_oos_fold(
            backtester,
            sample_events(),
            boundary_id=BOUNDARY_ID,
            fold=current_fold,
            selection_fold=selection,
            decision=decision,
            feature_ids=("different-feature",),
        )
