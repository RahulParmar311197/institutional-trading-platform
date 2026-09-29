import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from trading_platform.candles import Candle, CandleBuilder
from trading_platform.recorded_events import RecordedEventType, RecordedMarketEvent
from trading_platform.replay import ReplayStream

INSTRUMENT_ID = uuid.uuid4()
BASE = datetime(2026, 1, 1, 9, 15, tzinfo=UTC)


def recorded_trade(event_id: str, seconds: int, price: str) -> RecordedMarketEvent:
    timestamp = BASE + timedelta(seconds=seconds)
    return RecordedMarketEvent(
        event_id=event_id,
        event_type=RecordedEventType.TRADE,
        instrument_id=INSTRUMENT_ID,
        source="fixture",
        exchange_timestamp=timestamp,
        provider_timestamp=timestamp,
        ingestion_timestamp=timestamp,
        sequence=seconds,
        price=Decimal(price),
        quantity=1,
    )


def run_replay(events: list[RecordedMarketEvent]) -> list[Candle]:
    replay = ReplayStream.from_events(events)
    builder = CandleBuilder(INSTRUMENT_ID, interval=timedelta(minutes=1))
    closed: list[Candle] = []
    while (event := replay.next_event()) is not None:
        candle = builder.add(event.to_trade())
        if candle is not None:
            closed.append(candle)
    return closed


def test_repeated_replay_produces_identical_closed_candles() -> None:
    events = [
        recorded_trade("3", 60, "102"),
        recorded_trade("1", 0, "100"),
        recorded_trade("2", 30, "101"),
    ]

    first = run_replay(events)
    second = run_replay(events)

    assert first == second
    assert len(first) == 1
    assert first[0].open == Decimal("100")
    assert first[0].high == Decimal("101")
    assert first[0].low == Decimal("100")
    assert first[0].close == Decimal("101")
    assert first[0].volume == 2
