import uuid
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from trading_platform.candles import Candle
from trading_platform.indicators import ema


class SignalDirection(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


@dataclass(frozen=True, slots=True)
class StrategySignal:
    instrument_id: uuid.UUID
    direction: SignalDirection
    price: Decimal
    strategy_id: str
    reason: str


class EmaCrossoverStrategy:
    def __init__(self, *, fast_period: int = 5, slow_period: int = 20) -> None:
        if fast_period <= 0 or slow_period <= 0 or fast_period >= slow_period:
            raise ValueError("require 0 < fast_period < slow_period")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.strategy_id = f"ema_crossover_{fast_period}_{slow_period}"

    def evaluate(self, candles: list[Candle]) -> StrategySignal:
        if not candles:
            raise ValueError("at least one candle is required")
        if any(not candle.closed for candle in candles):
            raise ValueError("strategy may evaluate closed candles only")
        if len(candles) < self.slow_period + 1:
            raise ValueError("insufficient candles for strategy")

        closes = [candle.close for candle in candles]
        previous = closes[:-1]
        fast_previous = ema(previous, self.fast_period)
        slow_previous = ema(previous, self.slow_period)
        fast_current = ema(closes, self.fast_period)
        slow_current = ema(closes, self.slow_period)
        last = candles[-1]

        if fast_previous <= slow_previous and fast_current > slow_current:
            direction = SignalDirection.LONG
            reason = "FAST_EMA_CROSSED_ABOVE_SLOW_EMA"
        elif fast_previous >= slow_previous and fast_current < slow_current:
            direction = SignalDirection.SHORT
            reason = "FAST_EMA_CROSSED_BELOW_SLOW_EMA"
        else:
            direction = SignalDirection.FLAT
            reason = "NO_CROSSOVER"

        return StrategySignal(
            instrument_id=last.instrument_id,
            direction=direction,
            price=last.close,
            strategy_id=self.strategy_id,
            reason=reason,
        )
