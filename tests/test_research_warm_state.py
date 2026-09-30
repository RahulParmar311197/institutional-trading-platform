from dataclasses import replace
from datetime import timedelta

import pytest
from test_backtest import BASE, event, make_backtester

from trading_platform.pipeline import ReplayStrategyPipeline
from trading_platform.research_periods import ResearchWindow, WalkForwardFold
from trading_platform.research_warm_state import (
    PipelineWarmState,
    prepare_pipeline_warm_state,
)

BOUNDARY_ID = "research_boundaries_v1_fixture"
FEATURE_IDS = ("market_regime_v1_fixture",)


def fold() -> WalkForwardFold:
    return WalkForwardFold(
        index=0,
        train=ResearchWindow(
            start=BASE - timedelta(minutes=4),
            end=BASE,
        ),
        test=ResearchWindow(
            start=BASE + timedelta(minutes=1),
            end=BASE + timedelta(minutes=5),
        ),
        spec_id="walk_forward_v1_fixture",
    )


def source_event(event_id: str, minute: int, price: str):
    timestamp = BASE + timedelta(minutes=minute)
    return replace(
        event(event_id, 0, price),
        exchange_timestamp=timestamp,
        provider_timestamp=timestamp,
        ingestion_timestamp=timestamp,
    )


def prepared_state():
    current_fold = fold()
    return prepare_pipeline_warm_state(
        make_backtester(),
        [
            source_event("warm-1", -3, "100"),
            source_event("warm-2", -2, "99"),
            source_event("warm-3", -1, "101"),
        ],
        boundary_id=BOUNDARY_ID,
        fold=current_fold,
        source_window=current_fold.train,
        feature_ids=FEATURE_IDS,
    )


def test_warm_state_round_trip_is_deterministic_and_drops_pending_candle() -> None:
    prepared = prepared_state()
    serialized = prepared.state.to_bytes()
    restored = PipelineWarmState.from_bytes(serialized)

    assert restored == prepared.state
    assert restored.to_bytes() == serialized
    assert restored.state_digest == prepared.provenance.state_digest
    assert len(restored.closed_candles) == 2
    assert restored.closed_candles[-1].close == source_event("expected", -2, "99").price
    assert prepared.preparation_state_id == prepared.provenance.provenance_id


def test_warm_state_applies_only_to_compatible_fresh_pipeline() -> None:
    prepared = prepared_state()
    backtester = make_backtester()
    pipeline = ReplayStrategyPipeline(
        instrument_id=prepared.state.instrument_id,
        interval=backtester.interval,
        strategy=backtester.strategy,
    )

    prepared.state.apply_to_pipeline(pipeline)
    assert pipeline.closed_candles == prepared.state.closed_candles
    assert pipeline.checkpoint_state().pending_trades == ()

    with pytest.raises(ValueError, match="fresh replay pipeline"):
        prepared.state.apply_to_pipeline(pipeline)

    incompatible = ReplayStrategyPipeline(
        instrument_id=prepared.state.instrument_id,
        interval=timedelta(minutes=2),
        strategy=backtester.strategy,
    )
    with pytest.raises(ValueError, match="interval"):
        prepared.state.apply_to_pipeline(incompatible)


def test_warm_state_rejects_source_event_outside_train_window() -> None:
    current_fold = fold()
    with pytest.raises(ValueError, match="source_window"):
        prepare_pipeline_warm_state(
            make_backtester(),
            [
                source_event("warm-1", -3, "100"),
                source_event("test-leak", 1, "101"),
            ],
            boundary_id=BOUNDARY_ID,
            fold=current_fold,
            source_window=current_fold.train,
        )


def test_warm_state_rejects_tampered_or_malformed_serialization() -> None:
    prepared = prepared_state()
    serialized = prepared.state.to_bytes()

    with pytest.raises(ValueError, match="invalid fields"):
        PipelineWarmState.from_bytes(serialized[:-1] + b',"extra":1}')
    with pytest.raises(ValueError, match="invalid pipeline warm-state JSON"):
        PipelineWarmState.from_bytes(b"not-json")


def test_warm_state_identity_changes_with_closed_history() -> None:
    first = prepared_state()
    current_fold = fold()
    changed = prepare_pipeline_warm_state(
        make_backtester(),
        [
            source_event("warm-1", -3, "100"),
            source_event("warm-2", -2, "98"),
            source_event("warm-3", -1, "101"),
        ],
        boundary_id=BOUNDARY_ID,
        fold=current_fold,
        source_window=current_fold.train,
        feature_ids=FEATURE_IDS,
    )

    assert first.state.state_digest != changed.state.state_digest
    assert first.preparation_state_id != changed.preparation_state_id
