import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trading_platform.candles import CandleBuilder, Trade


def test_builder_closes_previous_bucket_without_future_trade_inclusion() -> None:
    instrument_id = uuid.uuid4()
    builder = CandleBuilder(instrument_id, interval=timedelta(minutes=1))
    base = datetime(2026, 1, 1, 9, 15, tzinfo=UTC)

    assert builder.add(Trade(instrument_id, base, Decimal("100"), 2)) is None
    assert builder.add(Trade(instrument_id, base + timedelta(seconds=30), Decimal("102"), 3)) is None
    closed = builder.add(Trade(instrument_id, base + timedelta(minutes=1), Decimal("200"), 5))

    assert closed is not None
    assert closed.open == Decimal("100")
    assert closed.high == Decimal("102")
    assert closed.low == Decimal("100")
    assert closed.close == Decimal("102")
    assert closed.volume == 5
    assert closed.closed is True

    current = builder.snapshot()
    assert current.open == Decimal("200")
    assert current.volume == 5
    assert current.closed is False


def test_builder_rejects_out_of_order_trade() -> None:
    instrument_id = uuid.uuid4()
    builder = CandleBuilder(instrument_id, interval=timedelta(minutes=1))
    base = datetime(2026, 1, 1, 9, 15, tzinfo=UTC)
    builder.add(Trade(instrument_id, base + timedelta(seconds=10), Decimal("100"), 1))

    with pytest.raises(ValueError, match="out-of-order"):
        builder.add(Trade(instrument_id, base, Decimal("99"), 1))
