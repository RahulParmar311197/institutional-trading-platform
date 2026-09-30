import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from trading_platform.recorded_events import (
    RecordedEventType,
    RecordedMarketEvent,
    normalize_recorded_events,
)
from trading_platform.replay import (
    ReplayCheckpoint,
    ReplayCheckpointFileStore,
    ReplayStream,
)

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


def test_replay_checkpoint_json_round_trip_preserves_resume_state() -> None:
    events = [
        event("1", seconds=0, sequence=1),
        event("2", seconds=1, sequence=2),
        event("3", seconds=2, sequence=3),
    ]
    original = ReplayStream.from_events(events)
    original.step(1)

    serialized = original.checkpoint().to_json()
    restored_checkpoint = ReplayCheckpoint.from_json(serialized)
    resumed = ReplayStream.from_events(events)
    resumed.restore(restored_checkpoint)

    assert resumed.cursor == 1
    assert tuple(item.event_id for item in resumed.step(10)) == ("2", "3")


def test_replay_checkpoint_file_store_round_trip_and_replace(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "replay.checkpoint.json"
    store = ReplayCheckpointFileStore(path)
    first = ReplayCheckpoint(cursor=1, event_count=3, stream_digest="0" * 64)
    second = ReplayCheckpoint(cursor=2, event_count=3, stream_digest="0" * 64)

    assert store.load() is None
    store.save(first)
    assert store.load() == first
    store.save(second)

    assert store.load() == second
    assert path.read_text(encoding="utf-8").endswith("\n")
    assert not tuple(path.parent.glob("*.tmp"))


def test_replay_checkpoint_file_store_supports_cross_process_style_restore(
    tmp_path: Path,
) -> None:
    events = [
        event("1", seconds=0, sequence=1),
        event("2", seconds=1, sequence=2),
        event("3", seconds=2, sequence=3),
    ]
    checkpoint_path = tmp_path / "job" / "checkpoint.json"
    first_store = ReplayCheckpointFileStore(checkpoint_path)
    first_process = ReplayStream.from_events(events)
    assert tuple(item.event_id for item in first_process.step(2)) == ("1", "2")
    first_store.save(first_process.checkpoint())

    second_store = ReplayCheckpointFileStore(checkpoint_path)
    persisted = second_store.load()
    assert persisted is not None
    second_process = ReplayStream.from_events(events)
    second_process.restore(persisted)

    assert tuple(item.event_id for item in second_process.step(10)) == ("3",)
    assert second_store.clear() is True
    assert second_store.clear() is False
    assert second_store.load() is None


def test_replay_checkpoint_file_store_rejects_corrupt_or_oversized_state(
    tmp_path: Path,
) -> None:
    path = tmp_path / "checkpoint.json"
    store = ReplayCheckpointFileStore(path)

    path.write_bytes(b"\xff")
    with pytest.raises(ValueError, match="valid UTF-8"):
        store.load()

    path.write_text("{" + ("x" * 5000), encoding="utf-8")
    with pytest.raises(ValueError, match="maximum size"):
        store.load()


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
    with pytest.raises(ValueError, match="invalid replay checkpoint JSON"):
        ReplayCheckpoint.from_json("{")
    with pytest.raises(ValueError, match="unexpected fields"):
        ReplayCheckpoint.from_json(
            '{"cursor":0,"event_count":0,"stream_digest":"'
            + digest
            + '","version":1,"extra":true}'
        )
    with pytest.raises(ValueError, match="cursor must be an integer"):
        ReplayCheckpoint.from_json(
            '{"cursor":true,"event_count":0,"stream_digest":"'
            + digest
            + '","version":1}'
        )


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
