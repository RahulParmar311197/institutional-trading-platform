from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from trading_platform.candles import Candle
from trading_platform.indicators import atr
from trading_platform.market_structure import TrendState


class VolatilityRegime(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"


@dataclass(frozen=True, slots=True)
class RegimeThresholds:
    low_atr_ratio: Decimal = Decimal("0.005")
    high_atr_ratio: Decimal = Decimal("0.02")

    def __post_init__(self) -> None:
        if self.low_atr_ratio < 0:
            raise ValueError("low_atr_ratio must be non-negative")
        if self.high_atr_ratio <= self.low_atr_ratio:
            raise ValueError("high_atr_ratio must be greater than low_atr_ratio")


@dataclass(frozen=True, slots=True)
class MarketRegime:
    trend: TrendState
    volatility: VolatilityRegime
    atr_ratio: Decimal


def classify_regime(
    candles: list[Candle],
    *,
    trend: TrendState,
    atr_period: int = 14,
    thresholds: RegimeThresholds | None = None,
) -> MarketRegime:
    if not candles:
        raise ValueError("regime classification requires candles")
    if any(not candle.closed for candle in candles):
        raise ValueError("regime classification requires closed candles only")
    if len({candle.instrument_id for candle in candles}) != 1:
        raise ValueError("regime classification requires one instrument")

    config = thresholds or RegimeThresholds()
    highs = [candle.high for candle in candles]
    lows = [candle.low for candle in candles]
    closes = [candle.close for candle in candles]
    current_atr = atr(highs, lows, closes, period=atr_period)
    last_close = closes[-1]
    if last_close <= 0:
        raise ValueError("last close must be positive")
    atr_ratio = current_atr / last_close

    if atr_ratio < config.low_atr_ratio:
        volatility = VolatilityRegime.LOW
    elif atr_ratio >= config.high_atr_ratio:
        volatility = VolatilityRegime.HIGH
    else:
        volatility = VolatilityRegime.NORMAL

    return MarketRegime(
        trend=trend,
        volatility=volatility,
        atr_ratio=atr_ratio,
    )
