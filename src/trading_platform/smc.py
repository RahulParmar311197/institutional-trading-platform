from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from trading_platform.candles import Candle


class GapDirection(StrEnum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


@dataclass(frozen=True, slots=True)
class FairValueGap:
    direction: GapDirection
    first_candle_index: int
    third_candle_index: int
    lower_bound: Decimal
    upper_bound: Decimal
    confirmed_at: datetime

    @property
    def midpoint(self) -> Decimal:
        return (self.lower_bound + self.upper_bound) / Decimal("2")


def detect_fair_value_gaps(candles: list[Candle]) -> list[FairValueGap]:
    if any(not candle.closed for candle in candles):
        raise ValueError("FVG detection requires closed candles only")
    if len(candles) < 3:
        return []

    gaps: list[FairValueGap] = []
    for index in range(2, len(candles)):
        first = candles[index - 2]
        third = candles[index]

        if third.low > first.high:
            gaps.append(
                FairValueGap(
                    direction=GapDirection.BULLISH,
                    first_candle_index=index - 2,
                    third_candle_index=index,
                    lower_bound=first.high,
                    upper_bound=third.low,
                    confirmed_at=third.end,
                )
            )
        elif third.high < first.low:
            gaps.append(
                FairValueGap(
                    direction=GapDirection.BEARISH,
                    first_candle_index=index - 2,
                    third_candle_index=index,
                    lower_bound=third.high,
                    upper_bound=first.low,
                    confirmed_at=third.end,
                )
            )
    return gaps
