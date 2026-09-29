import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trading_platform.recorded_events import (
    RecordedEventType,
    RecordedMarketEvent,
    normalize_recorded_events,
)
from trading_platform.replay import ReplayStream

INSTRUMENT_ID = uuid.uuid4()
BASE = datetime(2026, 1, 1, 9, 15, tzinfo=UTC)


def event(
    event_id: str,
    *,
    seconds: int,
    sequence: int | None,
    price: str = "100",
) -> RecordedMarketEvent:
    exchange_timestamp = BASE + timedelta(seconds=seconds)
    return RecordedMarketEvent(
        event_id=event_id,
        event_type=RecordedEventType.TRADE,
        instrument_id=INSTRUMENT_ID,
        source="fixture",
        exchange_timestamp=exchange_timestamp,
        provider_timestamp=exchange_timestamp + timedelta(milliseconds=10),
        ingestion_timestamp=exchange_timestamp + timedelta(milliseconds=20),
        sequence=sequence,
        price=Decimal(price),
        quantity=1,
    )


def test_normalization_orders_events_and_deduplicates_identical_records() -> None:
    first = event("1", seconds=0, sequence=1)
    second = event("2", seconds=1, sequence=2)

    normalized = normalize_recorded_events([second, first, first])

    assert normalized == (first, second)


def test_conflicting_duplicate_event_is_rejected() -> None:
    original = event("1", seconds=0, sequence=1, price="100")
    conflicting = event("1", seconds=0, sequence=1, price="101")

    with pytest.raises(ValueError, match="conflicting duplicate"):
        normalize_recorded_events([original, conflicting])


def test_replay_reset_produces_identical_sequence() -> None:
    events = [
        event("2", seconds=1, sequence=2),
        event("1", seconds=0, sequence=1),
    ]
    replay = ReplayStream.from_events(events)

    first_pass = replay.step(2)
    assert replay.remaining == 0

    replay.reset()
    second_pass = replay.step(2)

    assert first_pass == second_pass
    assert tuple(item.event_id for item in first_pass) == ("1", "2")


def test_recorded_event_requires_timezone_aware_timestamps() -> None:
    naive = datetime(2026, 1, 1, 9, 15)

    with pytest.raises(ValueError, match="timezone-aware"):
        RecordedMarketEvent(
            event_id="bad",
            event_type=RecordedEventType.TRADE,
            instrument_id=INSTRUMENT_ID,
            source="fixture",
            exchange_timestamp=naive,
            provider_timestamp=None,
            ingestion_timestamp=BASE,
            sequence=1,
            price=Decimal("100"),
            quantity=1,
        )
