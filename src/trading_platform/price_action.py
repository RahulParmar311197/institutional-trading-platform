from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from trading_platform.candles import Candle


class SwingType(StrEnum):
    HIGH = "HIGH"
    LOW = "LOW"


class BreakDirection(StrEnum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


@dataclass(frozen=True, slots=True)
class ConfirmedSwing:
    type: SwingType
    candle_index: int
    price: Decimal
    occurred_at: datetime
    confirmed_at: datetime


@dataclass(frozen=True, slots=True)
class StructureBreak:
    direction: BreakDirection
    swing: ConfirmedSwing
    break_candle_index: int
    break_price: Decimal
    occurred_at: datetime


def detect_confirmed_swings(
    candles: list[Candle],
    *,
    left: int = 2,
    right: int = 2,
) -> list[ConfirmedSwing]:
    if left <= 0 or right <= 0:
        raise ValueError("left and right confirmation windows must be positive")
    if any(not candle.closed for candle in candles):
        raise ValueError("swing detection requires closed candles only")
    if len(candles) < left + right + 1:
        return []

    swings: list[ConfirmedSwing] = []
    for index in range(left, len(candles) - right):
        candle = candles[index]
        left_candles = candles[index - left : index]
        right_candles = candles[index + 1 : index + right + 1]
        neighbors = [*left_candles, *right_candles]
        confirmed_at = candles[index + right].end

        if all(candle.high > neighbor.high for neighbor in neighbors):
            swings.append(
                ConfirmedSwing(
                    type=SwingType.HIGH,
                    candle_index=index,
                    price=candle.high,
                    occurred_at=candle.end,
                    confirmed_at=confirmed_at,
                )
            )
        if all(candle.low < neighbor.low for neighbor in neighbors):
            swings.append(
                ConfirmedSwing(
                    type=SwingType.LOW,
                    candle_index=index,
                    price=candle.low,
                    occurred_at=candle.end,
                    confirmed_at=confirmed_at,
                )
            )
    return swings


def detect_structure_breaks(
    candles: list[Candle],
    swings: list[ConfirmedSwing],
) -> list[StructureBreak]:
    if any(not candle.closed for candle in candles):
        raise ValueError("structure detection requires closed candles only")

    breaks: list[StructureBreak] = []
    for swing in swings:
        for index, candle in enumerate(candles):
            if candle.end <= swing.confirmed_at:
                continue
            if swing.type is SwingType.HIGH and candle.close > swing.price:
                breaks.append(
                    StructureBreak(
                        direction=BreakDirection.BULLISH,
                        swing=swing,
                        break_candle_index=index,
                        break_price=candle.close,
                        occurred_at=candle.end,
                    )
                )
                break
            if swing.type is SwingType.LOW and candle.close < swing.price:
                breaks.append(
                    StructureBreak(
                        direction=BreakDirection.BEARISH,
                        swing=swing,
                        break_candle_index=index,
                        break_price=candle.close,
                        occurred_at=candle.end,
                    )
                )
                break
    return breaks
