from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from trading_platform.candles import Candle
from trading_platform.indicators import atr
from trading_platform.market_structure import StructureEvent, StructureEventType
from trading_platform.price_action import BreakDirection


@dataclass(frozen=True, slots=True)
class DisplacementConfig:
    atr_period: int = 3
    min_body_atr_multiple: Decimal = Decimal("1")

    def __post_init__(self) -> None:
        if self.atr_period <= 0:
            raise ValueError("atr_period must be positive")
        if self.min_body_atr_multiple <= 0:
            raise ValueError("min_body_atr_multiple must be positive")


@dataclass(frozen=True, slots=True)
class MarketStructureShift:
    direction: BreakDirection
    structure_event: StructureEvent
    displacement_body: Decimal
    atr_at_break: Decimal
    confirmed_at: datetime

    @property
    def body_atr_multiple(self) -> Decimal:
        return self.displacement_body / self.atr_at_break


def detect_market_structure_shifts(
    candles: list[Candle],
    structure_events: tuple[StructureEvent, ...],
    *,
    config: DisplacementConfig | None = None,
) -> tuple[MarketStructureShift, ...]:
    if any(not candle.closed for candle in candles):
        raise ValueError("MSS detection requires closed candles only")
    if len({candle.instrument_id for candle in candles}) > 1:
        raise ValueError("MSS detection requires one instrument")

    settings = config or DisplacementConfig()
    shifts: list[MarketStructureShift] = []

    for event in structure_events:
        if event.type is not StructureEventType.CHOCH:
            continue

        break_index = event.break_event.break_candle_index
        if break_index < 0 or break_index >= len(candles):
            raise ValueError("structure event break index is outside candle history")
        if break_index < settings.atr_period:
            continue

        break_candle = candles[break_index]
        if break_candle.end != event.break_event.occurred_at:
            raise ValueError("structure event time does not match break candle")

        direction_aligned = (
            event.direction is BreakDirection.BULLISH
            and break_candle.close > break_candle.open
        ) or (
            event.direction is BreakDirection.BEARISH
            and break_candle.close < break_candle.open
        )
        if not direction_aligned:
            continue

        available = candles[: break_index + 1]
        current_atr = atr(
            [candle.high for candle in available],
            [candle.low for candle in available],
            [candle.close for candle in available],
            period=settings.atr_period,
        )
        body = abs(break_candle.close - break_candle.open)
        if body < current_atr * settings.min_body_atr_multiple:
            continue

        shifts.append(
            MarketStructureShift(
                direction=event.direction,
                structure_event=event,
                displacement_body=body,
                atr_at_break=current_atr,
                confirmed_at=break_candle.end,
            )
        )

    return tuple(shifts)
