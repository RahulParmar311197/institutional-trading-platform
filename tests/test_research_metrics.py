from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trading_platform.research_metrics import (
    RiskAdjustedMetricSpec,
    calculate_risk_adjusted_metrics,
)
from trading_platform.research_returns import PeriodicReturn, ReturnPeriodSpec

BASE = datetime(2026, 1, 1, tzinfo=UTC)
DAY = timedelta(days=1)


def periodic_return(index: int, value: str) -> PeriodicReturn:
    start = BASE + index * DAY
    return PeriodicReturn(
        period_start=start,
        period_end=start + DAY,
        simple_return=Decimal(value),
    )


def test_sharpe_uses_sample_standard_deviation_and_explicit_annualization() -> None:
    returns = (
        periodic_return(0, "0.01"),
        periodic_return(1, "0.02"),
        periodic_return(2, "0.03"),
    )
    spec = ReturnPeriodSpec(period=DAY, periods_per_year=Decimal("1"))

    metrics = calculate_risk_adjusted_metrics(returns, return_spec=spec)

    assert metrics.observation_count == 3
    assert metrics.mean_return == Decimal("0.02")
    assert metrics.sample_stddev == Decimal("0.01")
    assert metrics.sharpe_ratio == Decimal("2")
    assert metrics.downside_deviation == 0
    assert metrics.sortino_ratio is None


def test_sortino_uses_population_lower_partial_moment_over_all_periods() -> None:
    returns = (
        periodic_return(0, "-0.01"),
        periodic_return(1, "0.03"),
    )
    spec = ReturnPeriodSpec(period=DAY, periods_per_year=Decimal("1"))

    metrics = calculate_risk_adjusted_metrics(returns, return_spec=spec)

    assert metrics.mean_return == Decimal("0.01")
    assert metrics.downside_deviation > 0
    assert metrics.sortino_ratio is not None
    assert metrics.sortino_ratio * metrics.sortino_ratio == pytest.approx(Decimal("2"))


def test_risk_free_rate_and_downside_target_are_explicit_per_period_inputs() -> None:
    returns = (
        periodic_return(0, "0.01"),
        periodic_return(1, "0.03"),
    )
    return_spec = ReturnPeriodSpec(period=DAY, periods_per_year=Decimal("4"))
    metric_spec = RiskAdjustedMetricSpec(
        risk_free_rate_per_period=Decimal("0.01"),
        downside_target_per_period=Decimal("0.02"),
    )

    metrics = calculate_risk_adjusted_metrics(
        returns,
        return_spec=return_spec,
        metric_spec=metric_spec,
    )

    assert metrics.sharpe_ratio is not None
    assert metrics.sharpe_ratio * metrics.sharpe_ratio == pytest.approx(Decimal("2"))
    assert metrics.sortino_ratio == Decimal("0")


def test_annualized_metrics_require_explicit_periods_per_year() -> None:
    returns = (periodic_return(0, "0.01"), periodic_return(1, "0.02"))

    with pytest.raises(ValueError, match="periods_per_year"):
        calculate_risk_adjusted_metrics(
            returns,
            return_spec=ReturnPeriodSpec(period=DAY),
        )


def test_metrics_reject_noncontiguous_or_wrong_period_returns() -> None:
    return_spec = ReturnPeriodSpec(period=DAY, periods_per_year=Decimal("252"))
    noncontiguous = (
        periodic_return(0, "0.01"),
        PeriodicReturn(
            period_start=BASE + 2 * DAY,
            period_end=BASE + 3 * DAY,
            simple_return=Decimal("0.02"),
        ),
    )
    wrong_period = (
        periodic_return(0, "0.01"),
        PeriodicReturn(
            period_start=BASE + DAY,
            period_end=BASE + DAY + timedelta(hours=12),
            simple_return=Decimal("0.02"),
        ),
    )

    with pytest.raises(ValueError, match="contiguous"):
        calculate_risk_adjusted_metrics(noncontiguous, return_spec=return_spec)
    with pytest.raises(ValueError, match="explicit return period"):
        calculate_risk_adjusted_metrics(wrong_period, return_spec=return_spec)


def test_zero_dispersion_returns_none_instead_of_infinite_ratios() -> None:
    returns = (periodic_return(0, "0"), periodic_return(1, "0"))
    spec = ReturnPeriodSpec(period=DAY, periods_per_year=Decimal("252"))

    metrics = calculate_risk_adjusted_metrics(returns, return_spec=spec)

    assert metrics.sample_stddev == 0
    assert metrics.downside_deviation == 0
    assert metrics.sharpe_ratio is None
    assert metrics.sortino_ratio is None
