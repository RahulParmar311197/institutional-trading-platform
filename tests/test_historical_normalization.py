import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trading_platform.historical_normalization import bars_to_closed_candles
from trading_platform.provider_historical import HistoricalBar

INSTRUMENT_ID = uuid.uuid4()


def bar(minute: int, *, close: str) -> HistoricalBar:
    return HistoricalBar(
        timestamp=datetime(2025, 1, 1, 9, 15, tzinfo=UTC) + timedelta(minutes=minute),
        open=Decimal("100"),
        high=Decimal("105"),
        low=Decimal("95"),
        close=Decimal(close),
        volume=100 + minute,
        open_interest=10,
        source="fixture",
    )


def test_provider_bars_become_sorted_closed_candles_without_trade_fabrication() -> None:
    candles = bars_to_closed_candles(
        instrument_id=INSTRUMENT_ID,
        bars=(bar(1, close="102"), bar(0, close="101")),
        interval=timedelta(minutes=1),
    )

    assert [candle.close for candle in candles] == [Decimal("101"), Decimal("102")]
    assert all(candle.closed for candle in candles)
    assert all(candle.instrument_id == INSTRUMENT_ID for candle in candles)
    assert candles[0].start == datetime(2025, 1, 1, 9, 15, tzinfo=UTC)
    assert candles[0].end == datetime(2025, 1, 1, 9, 16, tzinfo=UTC)
    assert candles[0].open == Decimal("100")
    assert candles[0].high == Decimal("105")
    assert candles[0].low == Decimal("95")
    assert candles[0].volume == 100


def test_provider_bar_normalization_rejects_duplicate_timestamps() -> None:
    duplicated = bar(0, close="101")

    with pytest.raises(ValueError, match="duplicate timestamps"):
        bars_to_closed_candles(
            instrument_id=INSTRUMENT_ID,
            bars=(duplicated, duplicated),
            interval=timedelta(minutes=1),
        )


def test_provider_bar_normalization_rejects_non_positive_interval() -> None:
    with pytest.raises(ValueError, match="interval must be positive"):
        bars_to_closed_candles(
            instrument_id=INSTRUMENT_ID,
            bars=(bar(0, close="101"),),
            interval=timedelta(0),
        )
