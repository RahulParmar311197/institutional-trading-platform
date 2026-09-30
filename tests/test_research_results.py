from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from test_backtest import make_backtester, sample_events

from trading_platform.replay import ReplayStream
from trading_platform.research_periods import (
    ResearchWindow,
    WalkForwardSpec,
    generate_walk_forward_folds,
)
from trading_platform.research_results import OOSBacktestResult, OOSProvenance

BASE = datetime(2026, 1, 1, tzinfo=UTC)
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


def make_provenance() -> OOSProvenance:
    spec = WalkForwardSpec(
        train_length=timedelta(days=5),
        test_length=timedelta(days=2),
        step=timedelta(days=1),
        embargo=timedelta(hours=1),
    )
    fold = generate_walk_forward_folds(
        ResearchWindow(start=BASE, end=BASE + timedelta(days=7, hours=1)),
        spec=spec,
    )[0]
    return OOSProvenance(
        boundary_id="research_boundaries_v1_fixture",
        fold_id=fold.fold_id,
        fold_spec_id=fold.spec_id,
        strategy_id="strategy.test.v1",
        feature_ids=("market_regime_v1_fixture",),
        stream_digest=DIGEST_A,
        backtest_config_digest=DIGEST_B,
        slippage_bps=Decimal("1.00"),
        fee_per_filled_order=Decimal("2.00"),
    )


def test_oos_provenance_identity_is_stable_and_parameter_sensitive() -> None:
    provenance = make_provenance()
    equivalent = replace(
        provenance,
        slippage_bps=Decimal("1.0"),
        fee_per_filled_order=Decimal("2.000"),
    )

    assert provenance.provenance_id.startswith("oos_provenance_v1_")
    assert provenance.provenance_id == equivalent.provenance_id
    assert provenance.provenance_id != replace(
        provenance,
        strategy_id="strategy.test.v2",
    ).provenance_id
    assert provenance.provenance_id != replace(
        provenance,
        feature_ids=("market_regime_v2_fixture",),
    ).provenance_id


def test_oos_provenance_rejects_ambiguous_or_invalid_identity() -> None:
    provenance = make_provenance()

    with pytest.raises(ValueError, match="duplicates"):
        replace(provenance, feature_ids=("feature.a", "feature.a"))
    with pytest.raises(ValueError, match="stream_digest"):
        replace(provenance, stream_digest="not-a-digest")
    with pytest.raises(ValueError, match="strategy_id"):
        replace(provenance, strategy_id=" ")
    with pytest.raises(ValueError, match="slippage_bps"):
        replace(provenance, slippage_bps=Decimal("-1"))


def test_oos_provenance_can_bind_real_backtest_configuration_and_stream() -> None:
    events = sample_events()
    backtester = make_backtester()
    session = backtester.create_session(events)
    fold = generate_walk_forward_folds(
        ResearchWindow(start=BASE, end=BASE + timedelta(days=7)),
        spec=WalkForwardSpec(
            train_length=timedelta(days=5),
            test_length=timedelta(days=2),
            step=timedelta(days=1),
        ),
    )[0]
    strategy_id = backtester.strategy.strategy_id

    provenance = OOSProvenance.from_fold(
        boundary_id="research_boundaries_v1_fixture",
        fold=fold,
        strategy_id=strategy_id,
        feature_ids=("market_regime_v1_fixture",),
        stream_digest=ReplayStream.from_events(events).stream_digest,
        backtest_config_digest=backtester.checkpoint_config_digest(),
        assumptions=backtester.assumptions,
    )

    assert provenance.fold_id == fold.fold_id
    assert provenance.fold_spec_id == fold.spec_id
    assert provenance.strategy_id == strategy_id
    assert provenance.stream_digest == session.replay.stream_digest


def test_oos_result_identity_binds_full_backtest_result_and_provenance() -> None:
    result = make_backtester().run(sample_events())
    provenance = make_provenance()
    envelope = OOSBacktestResult(provenance=provenance, result=result)

    assert envelope.result_id.startswith("oos_result_v1_")
    assert envelope.result_id == OOSBacktestResult(
        provenance=provenance,
        result=result,
    ).result_id
    assert envelope.result_id != OOSBacktestResult(
        provenance=replace(provenance, fold_id="walk_forward_fold_other"),
        result=result,
    ).result_id
    assert envelope.result_id != OOSBacktestResult(
        provenance=provenance,
        result=replace(result, final_equity=result.final_equity + Decimal("1")),
    ).result_id
