from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

RETURN_PERIOD_SPEC_VERSION = 1


@dataclass(frozen=True, slots=True)
class EquityObservation:
    timestamp: datetime
    equity: Decimal

    def __post_init__(self) -> None:
        _require_aware(self.timestamp, "timestamp")
        if self.equity <= 0:
            raise ValueError("equity must be positive")


@dataclass(frozen=True, slots=True)
class ReturnPeriodSpec:
    period: timedelta
    periods_per_year: Decimal | None = None
    version: int = RETURN_PERIOD_SPEC_VERSION

    def __post_init__(self) -> None:
        if self.version != RETURN_PERIOD_SPEC_VERSION:
            raise ValueError("unsupported return-period specification version")
        if self.period <= timedelta(0):
            raise ValueError("return period must be positive")
        if self.periods_per_year is not None and self.periods_per_year <= 0:
            raise ValueError("periods_per_year must be positive when provided")

    @property
    def spec_id(self) -> str:
        annualization = (
            _decimal_identity(self.periods_per_year)
            if self.periods_per_year is not None
            else "none"
        )
        return (
            f"return_period_v{self.version}_us{_timedelta_microseconds(self.period)}_"
            f"ppy{annualization}"
        )


@dataclass(frozen=True, slots=True)
class PeriodicReturn:
    period_start: datetime
    period_end: datetime
    simple_return: Decimal

    def __post_init__(self) -> None:
        _require_aware(self.period_start, "period_start")
        _require_aware(self.period_end, "period_end")
        if self.period_start >= self.period_end:
            raise ValueError("period_start must be before period_end")


def calculate_periodic_returns(
    observations: list[EquityObservation],
    *,
    spec: ReturnPeriodSpec,
) -> tuple[PeriodicReturn, ...]:
    if len(observations) < 2:
        raise ValueError("at least two equity observations are required")

    returns: list[PeriodicReturn] = []
    previous = observations[0]
    for current in observations[1:]:
        if current.timestamp <= previous.timestamp:
            raise ValueError("equity observations must be strictly increasing")
        if current.timestamp - previous.timestamp != spec.period:
            raise ValueError("equity observations must match the explicit return period")
        returns.append(
            PeriodicReturn(
                period_start=previous.timestamp,
                period_end=current.timestamp,
                simple_return=(current.equity / previous.equity) - Decimal("1"),
            )
        )
        previous = current
    return tuple(returns)


def _timedelta_microseconds(value: timedelta) -> int:
    return (
        (value.days * 86_400 + value.seconds) * 1_000_000
        + value.microseconds
    )


def _decimal_identity(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == 0:
        return "0"
    return format(normalized, "f")


def _require_aware(timestamp: datetime, name: str) -> None:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
