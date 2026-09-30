from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from trading_platform.research_returns import PeriodicReturn, ReturnPeriodSpec

RISK_ADJUSTED_METRICS_VERSION = 1


@dataclass(frozen=True, slots=True)
class RiskAdjustedMetricSpec:
    risk_free_rate_per_period: Decimal = Decimal("0")
    downside_target_per_period: Decimal = Decimal("0")
    version: int = RISK_ADJUSTED_METRICS_VERSION

    def __post_init__(self) -> None:
        if self.version != RISK_ADJUSTED_METRICS_VERSION:
            raise ValueError("unsupported risk-adjusted metric specification version")


@dataclass(frozen=True, slots=True)
class RiskAdjustedMetrics:
    observation_count: int
    mean_return: Decimal
    sample_stddev: Decimal
    downside_deviation: Decimal
    sharpe_ratio: Decimal | None
    sortino_ratio: Decimal | None


def calculate_risk_adjusted_metrics(
    returns: tuple[PeriodicReturn, ...],
    *,
    return_spec: ReturnPeriodSpec,
    metric_spec: RiskAdjustedMetricSpec | None = None,
) -> RiskAdjustedMetrics:
    if len(returns) < 2:
        raise ValueError("at least two periodic returns are required")
    if return_spec.periods_per_year is None:
        raise ValueError("periods_per_year must be explicit for annualized metrics")
    _validate_return_periods(returns, return_spec)

    config = metric_spec or RiskAdjustedMetricSpec()
    values = tuple(item.simple_return for item in returns)
    count = Decimal(len(values))
    mean_return = sum(values, Decimal("0")) / count

    squared_deviations = tuple((value - mean_return) ** 2 for value in values)
    sample_variance = sum(squared_deviations, Decimal("0")) / Decimal(
        len(values) - 1
    )
    sample_stddev = sample_variance.sqrt()

    downside_squares = tuple(
        min(value - config.downside_target_per_period, Decimal("0")) ** 2
        for value in values
    )
    downside_deviation = (sum(downside_squares, Decimal("0")) / count).sqrt()
    annualization = return_spec.periods_per_year.sqrt()

    mean_excess = mean_return - config.risk_free_rate_per_period
    sharpe_ratio = (
        mean_excess / sample_stddev * annualization
        if sample_stddev != 0
        else None
    )
    mean_above_target = mean_return - config.downside_target_per_period
    sortino_ratio = (
        mean_above_target / downside_deviation * annualization
        if downside_deviation != 0
        else None
    )

    return RiskAdjustedMetrics(
        observation_count=len(values),
        mean_return=mean_return,
        sample_stddev=sample_stddev,
        downside_deviation=downside_deviation,
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
    )


def _validate_return_periods(
    returns: tuple[PeriodicReturn, ...],
    return_spec: ReturnPeriodSpec,
) -> None:
    previous_end: datetime | None = None
    for item in returns:
        if item.period_end - item.period_start != return_spec.period:
            raise ValueError("periodic returns must match the explicit return period")
        if previous_end is not None and item.period_start != previous_end:
            raise ValueError("periodic returns must be contiguous and ordered")
        previous_end = item.period_end
