from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trading_platform.research_monte_carlo import (
    MovingBlockBootstrapSpec,
    moving_block_bootstrap,
)
from trading_platform.research_returns import PeriodicReturn, ReturnPeriodSpec

BASE = datetime(2026, 1, 1, tzinfo=UTC)
PERIOD_SPEC = ReturnPeriodSpec(period=timedelta(days=1), periods_per_year=Decimal("252"))


def return_series(values: tuple[str, ...]) -> tuple[PeriodicReturn, ...]:
    return tuple(
        PeriodicReturn(
            period_start=BASE + timedelta(days=index),
            period_end=BASE + timedelta(days=index + 1),
            simple_return=Decimal(value),
        )
        for index, value in enumerate(values)
    )


def test_moving_block_bootstrap_is_deterministic_and_identity_bound() -> None:
    source = return_series(("0.01", "-0.02", "0.03", "0.04", "-0.01", "0.02"))
    spec = MovingBlockBootstrapSpec(block_length=2, path_count=4, seed=17)

    first = moving_block_bootstrap(source, return_period_spec=PERIOD_SPEC, spec=spec)
    second = moving_block_bootstrap(source, return_period_spec=PERIOD_SPEC, spec=spec)

    assert first == second
    assert first.result_id == second.result_id
    assert first.spec_id == spec.spec_id
    assert first.return_period_spec_id == PERIOD_SPEC.spec_id
    assert len(first.paths) == 4
    assert all(len(path.simple_returns) == len(source) for path in first.paths)


def test_moving_block_bootstrap_preserves_contiguous_source_blocks() -> None:
    source = return_series(("0.01", "0.02", "0.03", "0.04", "0.05", "0.06"))
    spec = MovingBlockBootstrapSpec(block_length=2, path_count=5, seed=29)
    result = moving_block_bootstrap(source, return_period_spec=PERIOD_SPEC, spec=spec)
    source_values = tuple(item.simple_return for item in source)
    valid_blocks = {
        source_values[index : index + spec.block_length]
        for index in range(len(source_values) - spec.block_length + 1)
    }

    for path in result.paths:
        for offset in range(0, len(source_values), spec.block_length):
            block = path.simple_returns[offset : offset + spec.block_length]
            if len(block) == spec.block_length:
                assert block in valid_blocks


def test_moving_block_bootstrap_seed_and_source_change_identity() -> None:
    source = return_series(("0.01", "-0.02", "0.03", "0.04", "-0.01", "0.02"))
    first = moving_block_bootstrap(
        source,
        return_period_spec=PERIOD_SPEC,
        spec=MovingBlockBootstrapSpec(block_length=2, path_count=8, seed=1),
    )
    changed_seed = moving_block_bootstrap(
        source,
        return_period_spec=PERIOD_SPEC,
        spec=MovingBlockBootstrapSpec(block_length=2, path_count=8, seed=2),
    )
    changed_source = moving_block_bootstrap(
        return_series(("0.01", "-0.02", "0.03", "0.04", "-0.01", "0.03")),
        return_period_spec=PERIOD_SPEC,
        spec=MovingBlockBootstrapSpec(block_length=2, path_count=8, seed=1),
    )

    assert first.result_id != changed_seed.result_id
    assert first.source_digest != changed_source.source_digest
    assert first.result_id != changed_source.result_id


def test_bootstrap_path_cumulative_return_compounds_simple_returns() -> None:
    result = moving_block_bootstrap(
        return_series(("0.10", "-0.10")),
        return_period_spec=PERIOD_SPEC,
        spec=MovingBlockBootstrapSpec(block_length=2, path_count=1, seed=5),
    )

    assert result.paths[0].simple_returns == (Decimal("0.10"), Decimal("-0.10"))
    assert result.paths[0].cumulative_return == Decimal("-0.01")


def test_moving_block_bootstrap_rejects_invalid_specification() -> None:
    with pytest.raises(ValueError, match="block_length"):
        MovingBlockBootstrapSpec(block_length=0, path_count=1, seed=1)
    with pytest.raises(ValueError, match="path_count"):
        MovingBlockBootstrapSpec(block_length=1, path_count=True, seed=1)
    with pytest.raises(ValueError, match="seed"):
        MovingBlockBootstrapSpec(block_length=1, path_count=1, seed=True)


def test_moving_block_bootstrap_rejects_block_longer_than_source() -> None:
    with pytest.raises(ValueError, match="must not exceed"):
        moving_block_bootstrap(
            return_series(("0.01", "0.02")),
            return_period_spec=PERIOD_SPEC,
            spec=MovingBlockBootstrapSpec(block_length=3, path_count=1, seed=1),
        )


def test_moving_block_bootstrap_rejects_noncontiguous_or_wrong_period_returns() -> None:
    source = list(return_series(("0.01", "0.02", "0.03")))
    source[1] = PeriodicReturn(
        period_start=BASE + timedelta(days=2),
        period_end=BASE + timedelta(days=3),
        simple_return=Decimal("0.02"),
    )
    with pytest.raises(ValueError, match="contiguous"):
        moving_block_bootstrap(
            tuple(source),
            return_period_spec=PERIOD_SPEC,
            spec=MovingBlockBootstrapSpec(block_length=1, path_count=1, seed=1),
        )

    wrong_period = (
        PeriodicReturn(
            period_start=BASE,
            period_end=BASE + timedelta(hours=12),
            simple_return=Decimal("0.01"),
        ),
    )
    with pytest.raises(ValueError, match="explicit return period"):
        moving_block_bootstrap(
            wrong_period,
            return_period_spec=PERIOD_SPEC,
            spec=MovingBlockBootstrapSpec(block_length=1, path_count=1, seed=1),
        )


def test_moving_block_bootstrap_rejects_impossible_simple_return() -> None:
    with pytest.raises(ValueError, match="greater than -1"):
        moving_block_bootstrap(
            return_series(("-1",)),
            return_period_spec=PERIOD_SPEC,
            spec=MovingBlockBootstrapSpec(block_length=1, path_count=1, seed=1),
        )
