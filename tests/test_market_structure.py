from datetime import UTC, datetime, timedelta
from decimal import Decimal

from trading_platform.market_structure import (
    StructureEventType,
    TrendState,
    classify_structure_breaks,
)
from trading_platform.price_action import (
    BreakDirection,
    ConfirmedSwing,
    StructureBreak,
    SwingType,
)

BASE = datetime(2026, 1, 1, 9, 15, tzinfo=UTC)


def make_break(index: int, direction: BreakDirection) -> StructureBreak:
    swing_type = SwingType.HIGH if direction is BreakDirection.BULLISH else SwingType.LOW
    swing_price = Decimal("100") if direction is BreakDirection.BULLISH else Decimal("90")
    swing = ConfirmedSwing(
        type=swing_type,
        candle_index=index,
        price=swing_price,
        occurred_at=BASE + timedelta(minutes=index),
        confirmed_at=BASE + timedelta(minutes=index + 2),
    )
    break_price = Decimal("101") if direction is BreakDirection.BULLISH else Decimal("89")
    return StructureBreak(
        direction=direction,
        swing=swing,
        break_candle_index=index + 3,
        break_price=break_price,
        occurred_at=BASE + timedelta(minutes=index + 3),
    )


def test_first_directional_break_establishes_trend_as_bos() -> None:
    event = classify_structure_breaks([make_break(0, BreakDirection.BULLISH)])[0]

    assert event.type is StructureEventType.BOS
    assert event.trend_before is TrendState.UNKNOWN
    assert event.trend_after is TrendState.BULLISH


def test_same_direction_break_is_continuation_bos() -> None:
    events = classify_structure_breaks(
        [
            make_break(0, BreakDirection.BULLISH),
            make_break(10, BreakDirection.BULLISH),
        ]
    )

    assert events[1].type is StructureEventType.BOS
    assert events[1].trend_before is TrendState.BULLISH
    assert events[1].trend_after is TrendState.BULLISH


def test_opposite_confirmed_break_is_choch_and_flips_state() -> None:
    events = classify_structure_breaks(
        [
            make_break(0, BreakDirection.BULLISH),
            make_break(10, BreakDirection.BEARISH),
        ]
    )

    assert events[1].type is StructureEventType.CHOCH
    assert events[1].trend_before is TrendState.BULLISH
    assert events[1].trend_after is TrendState.BEARISH


def test_breaks_are_classified_in_event_time_order() -> None:
    later = make_break(10, BreakDirection.BEARISH)
    earlier = make_break(0, BreakDirection.BULLISH)

    events = classify_structure_breaks([later, earlier])

    assert events[0].break_event is earlier
    assert events[1].break_event is later
    assert events[1].type is StructureEventType.CHOCH
