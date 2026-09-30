from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trading_platform.research_returns import (
    EquityObservation,
    ReturnPeriodSpec,
    calculate_periodic_returns,
)

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def observation(day: int, equity: str) -> EquityObservation:
    return EquityObservation(
        timestamp=BASE + timedelta(days=day),
        equity=Decimal(equity),
    )


def test_periodic_returns_require_and_use_explicit_regular_periods() -> None:
    spec = ReturnPeriodSpec(period=timedelta(days=1))

    returns = calculate_periodic_returns(
        [observation(0, "100"), observation(1, "110"), observation(2, "99")],
        spec=spec,
    )

    assert [item.simple_return for item in returns] == [
        Decimal("0.1"),
        Decimal("-0.1"),
    ]
    assert returns[0].period_start == BASE
    assert returns[0].period_end == BASE + timedelta(days=1)


def test_periodic_returns_reject_irregular_or_non_monotonic_observations() -> None:
    spec = ReturnPeriodSpec(period=timedelta(days=1))

    with pytest.raises(ValueError, match="explicit return period"):
        calculate_periodic_returns(
            [observation(0, "100"), observation(2, "101")],
            spec=spec,
        )

    with pytest.raises(ValueError, match="strictly increasing"):
        calculate_periodic_returns(
            [observation(1, "100"), observation(0, "101")],
            spec=spec,
        )


def test_return_period_identity_is_versioned_and_decimal_canonical() -> None:
    first = ReturnPeriodSpec(
        period=timedelta(days=1),
        periods_per_year=Decimal("252.0"),
    )
    equivalent = ReturnPeriodSpec(
        period=timedelta(days=1),
        periods_per_year=Decimal("252"),
    )
    without_annualization = ReturnPeriodSpec(period=timedelta(days=1))

    assert first.spec_id == equivalent.spec_id
    assert first.spec_id != without_annualization.spec_id
    assert first.spec_id == "return_period_v1_us86400000000_ppy252"


def test_return_period_spec_does_not_infer_annualization() -> None:
    spec = ReturnPeriodSpec(period=timedelta(hours=1))

    assert spec.periods_per_year is None
    assert spec.spec_id.endswith("_ppynone")


def test_return_inputs_reject_naive_timestamps_and_non_positive_equity() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        EquityObservation(timestamp=datetime(2026, 1, 1), equity=Decimal("100"))

    with pytest.raises(ValueError, match="positive"):
        EquityObservation(timestamp=BASE, equity=Decimal("0"))


def test_return_period_spec_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="period must be positive"):
        ReturnPeriodSpec(period=timedelta(0))

    with pytest.raises(ValueError, match="periods_per_year"):
        ReturnPeriodSpec(period=timedelta(days=1), periods_per_year=Decimal("0"))

    with pytest.raises(ValueError, match="unsupported"):
        ReturnPeriodSpec(period=timedelta(days=1), version=2)


def test_periodic_returns_require_at_least_two_observations() -> None:
    with pytest.raises(ValueError, match="at least two"):
        calculate_periodic_returns(
            [observation(0, "100")],
            spec=ReturnPeriodSpec(period=timedelta(days=1)),
        )
