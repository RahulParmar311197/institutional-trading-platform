import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trading_platform.candles import Candle
from trading_platform.strategy import EmaCrossoverStrategy


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


def test_strategy_rejects_open_candle() -> None:
    strategy = EmaCrossoverStrategy(fast_period=2, slow_period=3)
    candles = [candle(0), candle(1), candle(2), candle(3, closed=False)]

    with pytest.raises(ValueError, match="closed candles only"):
        strategy.evaluate(candles)


def test_strategy_requires_sufficient_history() -> None:
    strategy = EmaCrossoverStrategy(fast_period=2, slow_period=3)

    with pytest.raises(ValueError, match="insufficient candles"):
        strategy.evaluate([candle(0), candle(1), candle(2)])
