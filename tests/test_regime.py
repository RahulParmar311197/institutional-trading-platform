import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trading_platform.candles import Candle
from trading_platform.market_structure import TrendState
from trading_platform.regime import (
    RegimeFeatureSpec,
    RegimeThresholds,
    VolatilityRegime,
    classify_regime,
)

INSTRUMENT_ID = uuid.uuid4()
BASE = datetime(2026, 1, 1, 9, 15, tzinfo=UTC)


def candle(
    index: int,
    *,
    high: str,
    low: str,
    close: str = "100",
    closed: bool = True,
) -> Candle:
    start = BASE + timedelta(minutes=index)
    return Candle(
        instrument_id=INSTRUMENT_ID,
        start=start,
        end=start + timedelta(minutes=1),
        open=Decimal(close),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=1,
        closed=closed,
    )


def test_regime_combines_existing_trend_with_low_volatility() -> None:
    candles = [
        candle(0, high="100.1", low="99.9"),
        candle(1, high="100.1", low="99.9"),
        candle(2, high="100.1", low="99.9"),
    ]

    result = classify_regime(candles, trend=TrendState.BULLISH, atr_period=2)

    assert result.feature_id == "market_regime_v1_atr2_low0.005_high0.02"
    assert result.instrument_id == INSTRUMENT_ID
    assert result.as_of == candles[-1].end
    assert result.trend is TrendState.BULLISH
    assert result.volatility is VolatilityRegime.LOW
    assert result.atr_ratio == Decimal("0.002")


def test_regime_feature_identity_is_parameter_specific_and_decimal_canonical() -> None:
    first = RegimeFeatureSpec(
        atr_period=2,
        thresholds=RegimeThresholds(
            low_atr_ratio=Decimal("0.0050"),
            high_atr_ratio=Decimal("0.0200"),
        ),
    )
    equivalent = RegimeFeatureSpec(
        atr_period=2,
        thresholds=RegimeThresholds(
            low_atr_ratio=Decimal("0.005"),
            high_atr_ratio=Decimal("0.02"),
        ),
    )
    changed = RegimeFeatureSpec(
        atr_period=3,
        thresholds=equivalent.thresholds,
    )

    assert first.feature_id == equivalent.feature_id
    assert changed.feature_id != equivalent.feature_id


def test_regime_classifies_normal_and_high_volatility_by_explicit_thresholds() -> None:
    thresholds = RegimeThresholds(
        low_atr_ratio=Decimal("0.005"),
        high_atr_ratio=Decimal("0.02"),
    )
    normal = [
        candle(0, high="100.5", low="99.5"),
        candle(1, high="100.5", low="99.5"),
        candle(2, high="100.5", low="99.5"),
    ]
    high = [
        candle(0, high="103", low="97"),
        candle(1, high="103", low="97"),
        candle(2, high="103", low="97"),
    ]

    normal_result = classify_regime(
        normal,
        trend=TrendState.UNKNOWN,
        atr_period=2,
        thresholds=thresholds,
    )
    high_result = classify_regime(
        high,
        trend=TrendState.BEARISH,
        atr_period=2,
        thresholds=thresholds,
    )

    assert normal_result.volatility is VolatilityRegime.NORMAL
    assert high_result.volatility is VolatilityRegime.HIGH
    assert high_result.trend is TrendState.BEARISH
    assert normal_result.feature_id == high_result.feature_id


def test_regime_rejects_open_candles() -> None:
    candles = [
        candle(0, high="101", low="99"),
        candle(1, high="101", low="99"),
        candle(2, high="101", low="99", closed=False),
    ]

    with pytest.raises(ValueError, match="closed candles only"):
        classify_regime(candles, trend=TrendState.UNKNOWN, atr_period=2)


def test_regime_feature_spec_rejects_invalid_period_or_version() -> None:
    with pytest.raises(ValueError, match="atr_period"):
        RegimeFeatureSpec(atr_period=0)
    with pytest.raises(ValueError, match="unsupported"):
        RegimeFeatureSpec(version=2)
