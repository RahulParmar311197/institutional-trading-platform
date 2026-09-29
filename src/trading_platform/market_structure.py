from dataclasses import dataclass
from enum import StrEnum

from trading_platform.price_action import BreakDirection, StructureBreak


class TrendState(StrEnum):
    UNKNOWN = "UNKNOWN"
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class StructureEventType(StrEnum):
    BOS = "BOS"
    CHOCH = "CHOCH"


@dataclass(frozen=True, slots=True)
class StructureEvent:
    type: StructureEventType
    direction: BreakDirection
    break_event: StructureBreak
    trend_before: TrendState
    trend_after: TrendState


def classify_structure_breaks(
    breaks: list[StructureBreak],
) -> tuple[StructureEvent, ...]:
    ordered = sorted(
        breaks,
        key=lambda item: (item.occurred_at, item.break_candle_index),
    )
    trend = TrendState.UNKNOWN
    events: list[StructureEvent] = []

    for item in ordered:
        direction_trend = (
            TrendState.BULLISH
            if item.direction is BreakDirection.BULLISH
            else TrendState.BEARISH
        )
        before = trend
        if trend is TrendState.UNKNOWN or trend is direction_trend:
            event_type = StructureEventType.BOS
        else:
            event_type = StructureEventType.CHOCH
        trend = direction_trend
        events.append(
            StructureEvent(
                type=event_type,
                direction=item.direction,
                break_event=item,
                trend_before=before,
                trend_after=trend,
            )
        )

    return tuple(events)
