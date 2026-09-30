from dataclasses import replace
from datetime import timedelta

import pytest
from test_backtest import BASE, event, make_backtester

from trading_platform.research_periods import ResearchWindow, WalkForwardFold
from trading_platform.research_state import ResearchStateKind, ResearchStateProvenance

BOUNDARY_ID = "research_boundaries_v1_fixture"
FEATURE_IDS = ("market_regime_v1_fixture",)


def fold() -> WalkForwardFold:
    return WalkForwardFold(
        index=0,
        train=ResearchWindow(
            start=BASE - timedelta(minutes=10),
            end=BASE - timedelta(minutes=2),
        ),
        test=ResearchWindow(
            start=BASE,
            end=BASE + timedelta(minutes=5),
        ),
        spec_id="walk_forward_v1_fixture",
    )


def source_event(event_id: str, minute: int):
    timestamp = BASE + timedelta(minutes=minute)
    return replace(
        event(event_id, 0, "100"),
        exchange_timestamp=timestamp,
        provider_timestamp=timestamp,
        ingestion_timestamp=timestamp,
    )


def test_fitted_state_binds_exact_train_window_and_serialized_state() -> None:
    current_fold = fold()
    provenance = ResearchStateProvenance.from_events(
        kind=ResearchStateKind.FITTED,
        boundary_id=BOUNDARY_ID,
        fold=current_fold,
        strategy_id=make_backtester().strategy.strategy_id,
        feature_ids=FEATURE_IDS,
        source_window=current_fold.train,
        source_events=[source_event("train-a", -9), source_event("train-b", -3)],
        serialized_state=b'{"ema_fast":"101","ema_slow":"99"}',
    )

    assert provenance.kind is ResearchStateKind.FITTED
    assert provenance.fold_id == current_fold.fold_id
    assert provenance.fold_spec_id == current_fold.spec_id
    assert provenance.source_window == current_fold.train
    assert provenance.provenance_id.startswith("research_state_v1_")


def test_warmup_state_requires_trailing_subset_of_train_window() -> None:
    current_fold = fold()
    warmup = ResearchWindow(
        start=BASE - timedelta(minutes=5),
        end=current_fold.train.end,
    )
    provenance = ResearchStateProvenance.from_events(
        kind=ResearchStateKind.WARMUP,
        boundary_id=BOUNDARY_ID,
        fold=current_fold,
        strategy_id=make_backtester().strategy.strategy_id,
        feature_ids=FEATURE_IDS,
        source_window=warmup,
        source_events=[source_event("warm-a", -5), source_event("warm-b", -3)],
        serialized_state=b"warmup-state-v1",
    )

    assert provenance.kind is ResearchStateKind.WARMUP
    assert provenance.source_window == warmup

    with pytest.raises(ValueError, match="end at the fold train boundary"):
        ResearchStateProvenance.from_events(
            kind=ResearchStateKind.WARMUP,
            boundary_id=BOUNDARY_ID,
            fold=current_fold,
            strategy_id=make_backtester().strategy.strategy_id,
            feature_ids=FEATURE_IDS,
            source_window=ResearchWindow(
                start=BASE - timedelta(minutes=5),
                end=BASE - timedelta(minutes=3),
            ),
            source_events=[source_event("early", -4)],
            serialized_state=b"state",
        )


def test_research_state_rejects_test_or_out_of_window_event_leakage() -> None:
    current_fold = fold()

    with pytest.raises(ValueError, match="confined to source_window"):
        ResearchStateProvenance.from_events(
            kind=ResearchStateKind.FITTED,
            boundary_id=BOUNDARY_ID,
            fold=current_fold,
            strategy_id=make_backtester().strategy.strategy_id,
            feature_ids=FEATURE_IDS,
            source_window=current_fold.train,
            source_events=[source_event("train", -3), source_event("test-leak", 0)],
            serialized_state=b"state",
        )


def test_research_state_identity_is_deterministic_and_state_sensitive() -> None:
    current_fold = fold()
    kwargs = dict(
        kind=ResearchStateKind.FITTED,
        boundary_id=BOUNDARY_ID,
        fold=current_fold,
        strategy_id=make_backtester().strategy.strategy_id,
        feature_ids=FEATURE_IDS,
        source_window=current_fold.train,
        source_events=[source_event("train-a", -9), source_event("train-b", -3)],
    )
    first = ResearchStateProvenance.from_events(
        **kwargs,
        serialized_state=b"state-a",
    )
    reordered = ResearchStateProvenance.from_events(
        **{**kwargs, "source_events": list(reversed(kwargs["source_events"]))},
        serialized_state=b"state-a",
    )
    changed = ResearchStateProvenance.from_events(
        **kwargs,
        serialized_state=b"state-b",
    )

    assert first.provenance_id == reordered.provenance_id
    assert first.provenance_id != changed.provenance_id
    assert first.source_stream_digest == reordered.source_stream_digest
    assert first.state_digest != changed.state_digest


def test_research_state_rejects_ambiguous_inputs() -> None:
    current_fold = fold()
    with pytest.raises(ValueError, match="serialized research state"):
        ResearchStateProvenance.from_events(
            kind=ResearchStateKind.FITTED,
            boundary_id=BOUNDARY_ID,
            fold=current_fold,
            strategy_id=make_backtester().strategy.strategy_id,
            feature_ids=FEATURE_IDS,
            source_window=current_fold.train,
            source_events=[source_event("train", -3)],
            serialized_state=b"",
        )

    with pytest.raises(ValueError, match="source events"):
        ResearchStateProvenance.from_events(
            kind=ResearchStateKind.FITTED,
            boundary_id=BOUNDARY_ID,
            fold=current_fold,
            strategy_id=make_backtester().strategy.strategy_id,
            feature_ids=FEATURE_IDS,
            source_window=current_fold.train,
            source_events=[],
            serialized_state=b"state",
        )
