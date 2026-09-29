from decimal import Decimal

import pytest

from trading_platform.indicators import ema, rsi, sma


def test_sma_uses_latest_window() -> None:
    values = [Decimal(value) for value in ["1", "2", "3", "4", "5"]]
    assert sma(values, 3) == Decimal("4")


def test_ema_rejects_insufficient_data() -> None:
    with pytest.raises(ValueError, match="insufficient"):
        ema([Decimal("1")], 2)


def test_rsi_is_100_for_only_gains() -> None:
    values = [Decimal(value) for value in ["1", "2", "3", "4", "5", "6"]]
    assert rsi(values, period=5) == Decimal("100")
