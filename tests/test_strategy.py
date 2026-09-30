import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trading_platform.candles import Candle
from trading_platform.strategy import (
    EMA_CROSSOVER_STRATEGY_VERSION,
    EmaCrossoverStrategy,
    StrategyLifecycle,
    StrategyRegistry,
)


def candle(index: int, *, closed: bool = True) -> Candle:
    instrument_id = TEST_INSTRUMENT_ID
    start = datetime(2026, 1, 1, 9, 15, tzinfo=UTC) + timedelta(minutes=index)
    price = Decimal(index + 100)
    return Candle(
        instrument_id=instrument_id,
        start=start,
        end=start + timedelta(minutes=1),
        open=price,
        high=price,
        low=price,
        close=price,
        volume=1,
        closed=closed,
    )


TEST_INSTRUMENT_ID = uuid.uuid4()


def test_strategy_identity_is_versioned_and_parameter_specific() -> None:
    first = EmaCrossoverStrategy(fast_period=2, slow_period=3)
    second = EmaCrossoverStrategy(fast_period=2, slow_period=4)

    assert first.strategy_id == "ema_crossover_v1_2_3"
    assert second.strategy_id == "ema_crossover_v1_2_4"
    assert first.strategy_id != second.strategy_id


def test_strategy_registry_resolves_immutable_active_version() -> None:
    registry = StrategyRegistry()
    descriptor = registry.register(
        lambda: EmaCrossoverStrategy(fast_period=2, slow_period=3),
        family="ema_crossover",
        version=EMA_CROSSOVER_STRATEGY_VERSION,
    )

    first = registry.create(descriptor.strategy_id)
    second = registry.create(descriptor.strategy_id)

    assert descriptor.strategy_id == "ema_crossover_v1_2_3"
    assert descriptor.family == "ema_crossover"
    assert descriptor.version == 1
    assert descriptor.minimum_history == 4
    assert descriptor.lifecycle is StrategyLifecycle.ACTIVE
    assert first is not second
    assert first.strategy_id == second.strategy_id == descriptor.strategy_id
    assert registry.descriptors == (descriptor,)


def test_strategy_registry_retirement_preserves_historical_resolution() -> None:
    registry = StrategyRegistry()
    descriptor = registry.register(
        lambda: EmaCrossoverStrategy(fast_period=2, slow_period=3),
        family="ema_crossover",
        version=1,
    )

    retired = registry.retire(descriptor.strategy_id)

    assert retired.lifecycle is StrategyLifecycle.RETIRED
    assert registry.retire(descriptor.strategy_id) == retired
    with pytest.raises(ValueError, match="retired"):
        registry.create(descriptor.strategy_id)
    historical = registry.create(descriptor.strategy_id, allow_retired=True)
    assert historical.strategy_id == descriptor.strategy_id


def test_strategy_registry_rejects_duplicate_or_mutating_factory() -> None:
    registry = StrategyRegistry()
    calls = 0

    def changing_factory() -> EmaCrossoverStrategy:
        nonlocal calls
        calls += 1
        if calls == 1:
            return EmaCrossoverStrategy(fast_period=2, slow_period=3)
        return EmaCrossoverStrategy(fast_period=2, slow_period=4)

    descriptor = registry.register(
        changing_factory,
        family="ema_crossover",
        version=1,
    )
    with pytest.raises(RuntimeError, match="different strategy identity"):
        registry.create(descriptor.strategy_id)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(
            lambda: EmaCrossoverStrategy(fast_period=2, slow_period=3),
            family="ema_crossover",
            version=1,
        )


def test_strategy_registry_rejects_invalid_registration_metadata() -> None:
    registry = StrategyRegistry()
    with pytest.raises(ValueError, match="family"):
        registry.register(
            lambda: EmaCrossoverStrategy(fast_period=2, slow_period=3),
            family="   ",
            version=1,
        )
    with pytest.raises(ValueError, match="version"):
        registry.register(
            lambda: EmaCrossoverStrategy(fast_period=2, slow_period=3),
            family="ema_crossover",
            version=0,
        )


def test_strategy_rejects_open_candle() -> None:
    strategy = EmaCrossoverStrategy(fast_period=2, slow_period=3)
    candles = [candle(0), candle(1), candle(2), candle(3, closed=False)]

    with pytest.raises(ValueError, match="closed candles only"):
        strategy.evaluate(candles)


def test_strategy_requires_sufficient_history() -> None:
    strategy = EmaCrossoverStrategy(fast_period=2, slow_period=3)

    with pytest.raises(ValueError, match="insufficient candles"):
        strategy.evaluate([candle(0), candle(1), candle(2)])
