import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trading_platform.recorded_events import (
    RecordedEventType,
    RecordedMarketEvent,
    normalize_recorded_events,
)
from trading_platform.replay import ReplayCheckpoint, ReplayStream

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


def test_replay_checkpoint_resumes_exactly_after_consumed_events() -> None:
    events = [
        event("3", seconds=2, sequence=3),
        event("1", seconds=0, sequence=1),
        event("2", seconds=1, sequence=2),
    ]
    first = ReplayStream.from_events(events)

    assert tuple(item.event_id for item in first.step(2)) == ("1", "2")
    checkpoint = first.checkpoint()
    uninterrupted_tail = first.step(10)

    resumed = ReplayStream.from_events(events)
    resumed.restore(checkpoint)
    resumed_tail = resumed.step(10)

    assert checkpoint.cursor == 2
    assert checkpoint.event_count == 3
    assert resumed_tail == uninterrupted_tail
    assert tuple(item.event_id for item in resumed_tail) == ("3",)


def test_replay_checkpoint_rejects_changed_stream_even_with_same_length() -> None:
    original = ReplayStream.from_events(
        [
            event("1", seconds=0, sequence=1, price="100"),
            event("2", seconds=1, sequence=2, price="101"),
        ]
    )
    original.step(1)
    checkpoint = original.checkpoint()

    changed = ReplayStream.from_events(
        [
            event("1", seconds=0, sequence=1, price="100"),
            event("2", seconds=1, sequence=2, price="102"),
        ]
    )

    with pytest.raises(ValueError, match="stream digest"):
        changed.restore(checkpoint)
    assert changed.cursor == 0


def test_replay_checkpoint_rejects_different_event_count() -> None:
    original = ReplayStream.from_events([event("1", seconds=0, sequence=1)])
    checkpoint = original.checkpoint()
    expanded = ReplayStream.from_events(
        [
            event("1", seconds=0, sequence=1),
            event("2", seconds=1, sequence=2),
        ]
    )

    with pytest.raises(ValueError, match="event count"):
        expanded.restore(checkpoint)
    assert expanded.cursor == 0


def test_replay_checkpoint_validates_serialized_state() -> None:
    digest = "0" * 64

    with pytest.raises(ValueError, match="cursor must not exceed"):
        ReplayCheckpoint(cursor=2, event_count=1, stream_digest=digest)
    with pytest.raises(ValueError, match="SHA-256"):
        ReplayCheckpoint(cursor=0, event_count=0, stream_digest="not-a-digest")
    with pytest.raises(ValueError, match="unsupported"):
        ReplayCheckpoint(cursor=0, event_count=0, stream_digest=digest, version=2)


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
