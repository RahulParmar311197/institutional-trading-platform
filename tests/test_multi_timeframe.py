import uuid
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from trading_platform.candles import Trade
from trading_platform.multi_timeframe import MultiTimeframeCandleEngine, SessionCandleBuilder
from trading_platform.sessions import TradingSession

IST = ZoneInfo("Asia/Kolkata")
SESSION = TradingSession(
    timezone=IST,
    open_time=time(9, 15),
    close_time=time(15, 30),
)


def make_trade(
    instrument_id: uuid.UUID,
    hour: int,
    minute: int,
    *,
    price: str = "100",
    quantity: int = 1,
) -> Trade:
    return Trade(
        instrument_id=instrument_id,
        timestamp=datetime(2026, 1, 5, hour, minute, tzinfo=IST),
        price=Decimal(price),
        quantity=quantity,
    )


def test_hourly_bucket_is_anchored_to_session_open() -> None:
    instrument_id = uuid.uuid4()
    builder = SessionCandleBuilder(
        instrument_id,
        interval=timedelta(hours=1),
        session=SESSION,
    )

    assert builder.add(make_trade(instrument_id, 9, 20, price="100")) is None
    closed = builder.add(make_trade(instrument_id, 10, 16, price="102"))

    assert closed is not None
    assert closed.start == datetime(2026, 1, 5, 9, 15, tzinfo=IST)
    assert closed.end == datetime(2026, 1, 5, 10, 15, tzinfo=IST)
    assert closed.close == Decimal("100")


def test_last_session_bucket_is_truncated_at_close() -> None:
    instrument_id = uuid.uuid4()
    builder = SessionCandleBuilder(
        instrument_id,
        interval=timedelta(hours=1),
        session=SESSION,
    )

    builder.add(make_trade(instrument_id, 15, 20, price="100"))
    current = builder.snapshot()

    assert current.start == datetime(2026, 1, 5, 15, 15, tzinfo=IST)
    assert current.end == datetime(2026, 1, 5, 15, 30, tzinfo=IST)


def test_trade_outside_session_is_rejected() -> None:
    instrument_id = uuid.uuid4()
    builder = SessionCandleBuilder(
        instrument_id,
        interval=timedelta(minutes=5),
        session=SESSION,
    )

    with pytest.raises(ValueError, match="outside"):
        builder.add(make_trade(instrument_id, 9, 14))


def test_multi_timeframe_engine_closes_each_interval_independently() -> None:
    instrument_id = uuid.uuid4()
    five_minutes = timedelta(minutes=5)
    one_hour = timedelta(hours=1)
    engine = MultiTimeframeCandleEngine(
        instrument_id,
        session=SESSION,
        intervals=(five_minutes, one_hour),
    )

    assert engine.add(make_trade(instrument_id, 9, 15, price="100")) == {}
    completed = engine.add(make_trade(instrument_id, 9, 20, price="101"))

    assert set(completed) == {five_minutes}
    assert completed[five_minutes].start == datetime(2026, 1, 5, 9, 15, tzinfo=IST)

    completed = engine.add(make_trade(instrument_id, 10, 15, price="102"))

    assert five_minutes in completed
    assert one_hour in completed
    assert completed[one_hour].start == datetime(2026, 1, 5, 9, 15, tzinfo=IST)
    assert completed[one_hour].end == datetime(2026, 1, 5, 10, 15, tzinfo=IST)
