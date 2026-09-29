from decimal import Decimal

import pytest

from trading_platform.indicators import atr, ema, rsi, sma, vwap


def test_sma_uses_latest_window() -> None:
    values = [Decimal(value) for value in ["1", "2", "3", "4", "5"]]
    assert sma(values, 3) == Decimal("4")


def test_ema_rejects_insufficient_data() -> None:
    with pytest.raises(ValueError, match="insufficient"):
        ema([Decimal("1")], 2)


def test_rsi_is_100_for_only_gains() -> None:
    values = [Decimal(value) for value in ["1", "2", "3", "4", "5", "6"]]
    assert rsi(values, period=5) == Decimal("100")


def test_atr_uses_wilder_smoothing() -> None:
    highs = [Decimal(value) for value in ["10", "12", "13", "15"]]
    lows = [Decimal(value) for value in ["8", "9", "10", "11"]]
    closes = [Decimal(value) for value in ["9", "11", "12", "14"]]

    result = atr(highs, lows, closes, period=2)

    assert result == Decimal("3.25")


def test_atr_rejects_mismatched_series() -> None:
    with pytest.raises(ValueError, match="equal length"):
        atr(
            [Decimal("10"), Decimal("11")],
            [Decimal("9")],
            [Decimal("9"), Decimal("10")],
            period=1,
        )


def test_vwap_is_volume_weighted() -> None:
    result = vwap(
        [Decimal("100"), Decimal("110")],
        [1, 3],
    )
    assert result == Decimal("107.5")


def test_vwap_rejects_zero_total_volume() -> None:
    with pytest.raises(ValueError, match="positive total volume"):
        vwap([Decimal("100")], [0])
