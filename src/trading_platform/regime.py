import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from trading_platform.candles import Candle
from trading_platform.indicators import atr
from trading_platform.market_structure import TrendState

REGIME_FEATURE_VERSION = 1


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
class RegimeFeatureSpec:
    atr_period: int = 14
    thresholds: RegimeThresholds = RegimeThresholds()
    version: int = REGIME_FEATURE_VERSION

    def __post_init__(self) -> None:
        if self.version != REGIME_FEATURE_VERSION:
            raise ValueError("unsupported regime feature version")
        if self.atr_period <= 0:
            raise ValueError("atr_period must be positive")

    @property
    def feature_id(self) -> str:
        return (
            f"market_regime_v{self.version}_atr{self.atr_period}_"
            f"low{_decimal_identity(self.thresholds.low_atr_ratio)}_"
            f"high{_decimal_identity(self.thresholds.high_atr_ratio)}"
        )


@dataclass(frozen=True, slots=True)
class MarketRegime:
    feature_id: str
    instrument_id: uuid.UUID
    as_of: datetime
    trend: TrendState
    volatility: VolatilityRegime
    atr_ratio: Decimal

    def __post_init__(self) -> None:
        if not self.feature_id:
            raise ValueError("feature_id must not be empty")
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        if self.atr_ratio < 0:
            raise ValueError("atr_ratio must be non-negative")


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
    instrument_ids = {candle.instrument_id for candle in candles}
    if len(instrument_ids) != 1:
        raise ValueError("regime classification requires one instrument")

    spec = RegimeFeatureSpec(
        atr_period=atr_period,
        thresholds=thresholds or RegimeThresholds(),
    )
    highs = [candle.high for candle in candles]
    lows = [candle.low for candle in candles]
    closes = [candle.close for candle in candles]
    current_atr = atr(highs, lows, closes, period=spec.atr_period)
    last = candles[-1]
    if last.close <= 0:
        raise ValueError("last close must be positive")
    atr_ratio = current_atr / last.close

    if atr_ratio < spec.thresholds.low_atr_ratio:
        volatility = VolatilityRegime.LOW
    elif atr_ratio >= spec.thresholds.high_atr_ratio:
        volatility = VolatilityRegime.HIGH
    else:
        volatility = VolatilityRegime.NORMAL

    return MarketRegime(
        feature_id=spec.feature_id,
        instrument_id=last.instrument_id,
        as_of=last.end,
        trend=trend,
        volatility=volatility,
        atr_ratio=atr_ratio,
    )


def _decimal_identity(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == 0:
        return "0"
    return format(normalized, "f")
