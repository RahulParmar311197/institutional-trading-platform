import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trading_platform.candles import Candle
from trading_platform.price_action import (
    BreakDirection,
    SwingType,
    detect_confirmed_swings,
    detect_structure_breaks,
)

INSTRUMENT_ID = uuid.uuid4()
BASE = datetime(2026, 1, 1, 9, 15, tzinfo=UTC)


def candle(
    index: int,
    *,
    high: str,
    low: str,
    close: str,
    closed: bool = True,
) -> Candle:
    start = BASE + timedelta(minutes=index)
    return Candle(
        instrument_id=INSTRUMENT_ID,
        start=start,
        end=start + timedelta(minutes=1),
        open=Decimal(close),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=1,
        closed=closed,
    )


def test_swing_is_not_available_before_right_confirmation_window() -> None:
    candles = [
        candle(0, high="10", low="8", close="9"),
        candle(1, high="12", low="9", close="11"),
        candle(2, high="15", low="10", close="14"),
        candle(3, high="13", low="10", close="12"),
    ]

    assert detect_confirmed_swings(candles, left=2, right=2) == []


def test_confirmed_swing_records_when_it_became_knowable() -> None:
    candles = [
        candle(0, high="10", low="8", close="9"),
        candle(1, high="12", low="9", close="11"),
        candle(2, high="15", low="10", close="14"),
        candle(3, high="13", low="10", close="12"),
        candle(4, high="12", low="9", close="10"),
    ]

    swings = detect_confirmed_swings(candles, left=2, right=2)

    high_swings = [swing for swing in swings if swing.type is SwingType.HIGH]
    assert len(high_swings) == 1
    swing = high_swings[0]
    assert swing.candle_index == 2
    assert swing.price == Decimal("15")
    assert swing.confirmed_at == candles[4].end


def test_structure_break_can_only_occur_after_swing_confirmation() -> None:
    candles = [
        candle(0, high="10", low="8", close="9"),
        candle(1, high="12", low="9", close="11"),
        candle(2, high="15", low="10", close="14"),
        candle(3, high="16", low="11", close="16"),
        candle(4, high="12", low="9", close="10"),
        candle(5, high="17", low="12", close="16"),
    ]
    swings = detect_confirmed_swings(candles[:5], left=2, right=2)

    breaks = detect_structure_breaks(candles, swings)

    bullish = [item for item in breaks if item.direction is BreakDirection.BULLISH]
    assert len(bullish) == 1
    assert bullish[0].break_candle_index == 5
    assert bullish[0].occurred_at > bullish[0].swing.confirmed_at


def test_price_action_rejects_open_candles() -> None:
    candles = [
        candle(0, high="10", low="8", close="9"),
        candle(1, high="12", low="9", close="11"),
        candle(2, high="15", low="10", close="14", closed=False),
        candle(3, high="13", low="10", close="12"),
        candle(4, high="12", low="9", close="10"),
    ]

    with pytest.raises(ValueError, match="closed candles only"):
        detect_confirmed_swings(candles, left=2, right=2)
