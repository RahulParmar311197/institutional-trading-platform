from dataclasses import replace
from datetime import timedelta

import pytest
from test_backtest import BASE, event, make_backtester, sample_events

from trading_platform.research_periods import ResearchWindow, WalkForwardFold
from trading_platform.walk_forward import evaluate_fixed_strategy_oos_fold

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
