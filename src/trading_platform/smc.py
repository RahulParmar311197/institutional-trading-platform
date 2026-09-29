from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from trading_platform.candles import Candle


class GapDirection(StrEnum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class GapState(StrEnum):
    OPEN = "OPEN"
    PARTIALLY_MITIGATED = "PARTIALLY_MITIGATED"
    FILLED = "FILLED"
    INVALIDATED = "INVALIDATED"


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


@dataclass(frozen=True, slots=True)
class GapLifecycle:
    state: GapState
    first_touched_at: datetime | None = None
    filled_at: datetime | None = None
    invalidated_at: datetime | None = None


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


def evaluate_gap_lifecycle(
    gap: FairValueGap,
    candles: list[Candle],
) -> GapLifecycle:
    if any(not candle.closed for candle in candles):
        raise ValueError("FVG lifecycle requires closed candles only")

    first_touched_at: datetime | None = None
    filled_at: datetime | None = None

    for candle in candles:
        if candle.end <= gap.confirmed_at:
            continue

        if gap.direction is GapDirection.BULLISH:
            if candle.close < gap.lower_bound:
                return GapLifecycle(
                    state=GapState.INVALIDATED,
                    first_touched_at=first_touched_at or candle.end,
                    filled_at=filled_at or candle.end,
                    invalidated_at=candle.end,
                )
            if candle.low <= gap.lower_bound:
                first_touched_at = first_touched_at or candle.end
                filled_at = filled_at or candle.end
            elif candle.low < gap.upper_bound:
                first_touched_at = first_touched_at or candle.end
        else:
            if candle.close > gap.upper_bound:
                return GapLifecycle(
                    state=GapState.INVALIDATED,
                    first_touched_at=first_touched_at or candle.end,
                    filled_at=filled_at or candle.end,
                    invalidated_at=candle.end,
                )
            if candle.high >= gap.upper_bound:
                first_touched_at = first_touched_at or candle.end
                filled_at = filled_at or candle.end
            elif candle.high > gap.lower_bound:
                first_touched_at = first_touched_at or candle.end

    if filled_at is not None:
        return GapLifecycle(
            state=GapState.FILLED,
            first_touched_at=first_touched_at,
            filled_at=filled_at,
        )
    if first_touched_at is not None:
        return GapLifecycle(
            state=GapState.PARTIALLY_MITIGATED,
            first_touched_at=first_touched_at,
        )
    return GapLifecycle(state=GapState.OPEN)
