import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from trading_platform.candles import Candle
from trading_platform.market_structure import StructureEvent, StructureEventType, TrendState
from trading_platform.price_action import (
    BreakDirection,
    ConfirmedSwing,
    StructureBreak,
    SwingType,
)
from trading_platform.smc_structure import DisplacementConfig, detect_market_structure_shifts

INSTRUMENT_ID = uuid.uuid4()
BASE = datetime(2026, 1, 1, 9, 15, tzinfo=UTC)


def candle(
    index: int,
    *,
    open_price: str = "100",
    high: str = "101",
    low: str = "99",
    close: str = "100",
) -> Candle:
    start = BASE + timedelta(minutes=index)
    return Candle(
        instrument_id=INSTRUMENT_ID,
        start=start,
        end=start + timedelta(minutes=1),
        open=Decimal(open_price),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=1,
        closed=True,
    )


def bullish_choch(break_candle: Candle, *, index: int = 3) -> StructureEvent:
    swing = ConfirmedSwing(
        type=SwingType.HIGH,
        candle_index=1,
        price=Decimal("101"),
        occurred_at=BASE + timedelta(minutes=2),
        confirmed_at=BASE + timedelta(minutes=3),
    )
    structure_break = StructureBreak(
        direction=BreakDirection.BULLISH,
        swing=swing,
        break_candle_index=index,
        break_price=break_candle.close,
        occurred_at=break_candle.end,
    )
    return StructureEvent(
        type=StructureEventType.CHOCH,
        direction=BreakDirection.BULLISH,
        break_event=structure_break,
        trend_before=TrendState.BEARISH,
        trend_after=TrendState.BULLISH,
    )


def test_choch_with_atr_sized_displacement_confirms_mss() -> None:
    break_candle = candle(3, high="105", low="99", close="104")
    candles = [candle(0), candle(1), candle(2), break_candle]
    event = bullish_choch(break_candle)

    shifts = detect_market_structure_shifts(
        candles,
        (event,),
        config=DisplacementConfig(atr_period=2, min_body_atr_multiple=Decimal("1")),
    )

    assert len(shifts) == 1
    shift = shifts[0]
    assert shift.direction is BreakDirection.BULLISH
    assert shift.displacement_body == Decimal("4")
    assert shift.atr_at_break == Decimal("4")
    assert shift.body_atr_multiple == Decimal("1")
    assert shift.confirmed_at == break_candle.end


def test_choch_without_displacement_is_not_mss() -> None:
    break_candle = candle(3, high="105", low="99", close="101")
    candles = [candle(0), candle(1), candle(2), break_candle]

    shifts = detect_market_structure_shifts(
        candles,
        (bullish_choch(break_candle),),
        config=DisplacementConfig(atr_period=2, min_body_atr_multiple=Decimal("1")),
    )

    assert shifts == ()


def test_bos_is_not_relabelled_as_mss() -> None:
    break_candle = candle(3, high="105", low="99", close="104")
    choch = bullish_choch(break_candle)
    bos = StructureEvent(
        type=StructureEventType.BOS,
        direction=choch.direction,
        break_event=choch.break_event,
        trend_before=TrendState.BULLISH,
        trend_after=TrendState.BULLISH,
    )

    assert detect_market_structure_shifts(
        [candle(0), candle(1), candle(2), break_candle],
        (bos,),
        config=DisplacementConfig(atr_period=2),
    ) == ()


def test_future_candles_do_not_change_already_confirmed_mss() -> None:
    break_candle = candle(3, high="105", low="99", close="104")
    prefix = [candle(0), candle(1), candle(2), break_candle]
    event = bullish_choch(break_candle)
    config = DisplacementConfig(atr_period=2)

    original = detect_market_structure_shifts(prefix, (event,), config=config)
    extended = detect_market_structure_shifts(
        [*prefix, candle(4, high="150", low="50", close="60")],
        (event,),
        config=config,
    )

    assert extended == original
