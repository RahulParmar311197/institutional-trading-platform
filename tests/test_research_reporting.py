from dataclasses import replace
from datetime import timedelta, timezone

import pytest
from test_backtest import BASE, make_backtester, sample_events

from trading_platform.research_periods import ResearchWindow, WalkForwardFold
from trading_platform.research_reporting import (
    WalkForwardFoldResult,
    build_walk_forward_report,
)
from trading_platform.research_results import OOSBacktestResult, OOSProvenance

BOUNDARY_ID = "research_boundaries_v1_fixture"
FEATURE_IDS = ("market_regime_v1_fixture",)
SPEC_ID = "walk_forward_v1_fixture"


def make_fold(index: int, test_start_minutes: int) -> WalkForwardFold:
    test_start = BASE + timedelta(minutes=test_start_minutes)
    return WalkForwardFold(
        index=index,
        train=ResearchWindow(
            start=test_start - timedelta(minutes=20),
            end=test_start - timedelta(minutes=10),
        ),
        test=ResearchWindow(
            start=test_start,
            end=test_start + timedelta(minutes=5),
        ),
        spec_id=SPEC_ID,
    )


def make_evaluation(
    fold: WalkForwardFold,
    *,
    stream_digest: str,
    strategy_id: str | None = None,
) -> WalkForwardFoldResult:
    backtester = make_backtester()
    result = backtester.run(sample_events())
    provenance = OOSProvenance.from_fold(
        boundary_id=BOUNDARY_ID,
        fold=fold,
        strategy_id=strategy_id or backtester.strategy.strategy_id,
        feature_ids=FEATURE_IDS,
        stream_digest=stream_digest,
        backtest_config_digest=backtester.checkpoint_config_digest(),
        assumptions=backtester.assumptions,
    )
    return WalkForwardFoldResult(
        fold=fold,
        result=OOSBacktestResult(provenance=provenance, result=result),
    )


def test_walk_forward_report_is_fold_level_and_allows_overlapping_test_windows() -> None:
    first = make_evaluation(make_fold(0, 0), stream_digest="a" * 64)
    second = make_evaluation(make_fold(1, 2), stream_digest="b" * 64)

    report = build_walk_forward_report((first, second))

    expected_return = first.result.result.metrics.total_return
    assert report.mean_fold_total_return == expected_return
    assert [fold.index for fold in report.folds] == [0, 1]
    assert [fold.trade_count for fold in report.folds] == [
        first.result.result.metrics.trade_count,
        second.result.result.metrics.trade_count,
    ]
    assert report.report_id.startswith("walk_forward_report_v1_")


def test_walk_forward_report_rejects_unordered_or_gapped_fold_results() -> None:
    first = make_evaluation(make_fold(0, 0), stream_digest="a" * 64)
    second = make_evaluation(make_fold(1, 2), stream_digest="b" * 64)
    gapped = make_evaluation(make_fold(2, 4), stream_digest="c" * 64)

    with pytest.raises(ValueError, match="ordered and contiguous"):
        build_walk_forward_report((second, first))
    with pytest.raises(ValueError, match="ordered and contiguous"):
        build_walk_forward_report((first, gapped))


def test_walk_forward_report_rejects_incompatible_provenance() -> None:
    first = make_evaluation(make_fold(0, 0), stream_digest="a" * 64)
    second = make_evaluation(
        make_fold(1, 2),
        stream_digest="b" * 64,
        strategy_id="different.strategy.v1",
    )

    with pytest.raises(ValueError, match="strategy_id"):
        build_walk_forward_report((first, second))


def test_fold_result_rejects_result_bound_to_different_fold() -> None:
    first_fold = make_fold(0, 0)
    second_fold = make_fold(1, 2)
    second_result = make_evaluation(second_fold, stream_digest="b" * 64).result

    with pytest.raises(ValueError, match="fold_id"):
        WalkForwardFoldResult(fold=first_fold, result=second_result)


def test_walk_forward_report_identity_is_timezone_canonical() -> None:
    fold = make_fold(0, 0)
    evaluation = make_evaluation(fold, stream_digest="a" * 64)
    report = build_walk_forward_report((evaluation,))

    plus_one = timezone(timedelta(hours=1))
    shifted_fold = replace(
        fold,
        train=ResearchWindow(
            start=fold.train.start.astimezone(plus_one),
            end=fold.train.end.astimezone(plus_one),
        ),
        test=ResearchWindow(
            start=fold.test.start.astimezone(plus_one),
            end=fold.test.end.astimezone(plus_one),
        ),
    )
    shifted_evaluation = WalkForwardFoldResult(
        fold=shifted_fold,
        result=evaluation.result,
    )
    shifted_report = build_walk_forward_report((shifted_evaluation,))

    assert fold.fold_id == shifted_fold.fold_id
    assert report.report_id == shifted_report.report_id


def test_walk_forward_report_requires_at_least_one_fold() -> None:
    with pytest.raises(ValueError, match="at least one fold"):
        build_walk_forward_report(())
