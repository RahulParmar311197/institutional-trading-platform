import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from trading_platform.recorded_events import RecordedEventType, RecordedMarketEvent
from trading_platform.recorded_io import load_recorded_events_jsonl, write_recorded_events_jsonl


def event(
    instrument_id: uuid.UUID,
    *,
    event_id: str,
    minute: int,
    price: str,
) -> RecordedMarketEvent:
    timestamp = datetime(2026, 1, 1, 9, 15, tzinfo=UTC) + timedelta(minutes=minute)
    return RecordedMarketEvent(
        event_id=event_id,
        event_type=RecordedEventType.TRADE,
        instrument_id=instrument_id,
        source="recorded-jsonl-fixture",
        exchange_timestamp=timestamp,
        provider_timestamp=timestamp + timedelta(milliseconds=20),
        ingestion_timestamp=timestamp + timedelta(milliseconds=40),
        sequence=minute,
        price=Decimal(price),
        quantity=minute + 1,
    )


def test_recorded_jsonl_round_trip_is_lossless_and_normalized(tmp_path: Path) -> None:
    instrument_id = uuid.uuid4()
    events = [
        event(instrument_id, event_id="2", minute=1, price="100.25"),
        event(instrument_id, event_id="1", minute=0, price="99.95"),
    ]
    path = tmp_path / "events.jsonl"

    write_recorded_events_jsonl(path, events)
    loaded = load_recorded_events_jsonl(path)

    assert loaded == (events[1], events[0])
    assert loaded[0].price == Decimal("99.95")
    assert loaded[0].provider_timestamp == events[1].provider_timestamp


def test_recorded_jsonl_rejects_non_object_lines(tmp_path: Path) -> None:
    path = tmp_path / "invalid.jsonl"
    path.write_text('["not", "an", "event"]\n', encoding="utf-8")

    with pytest.raises(ValueError, match="must be a JSON object"):
        load_recorded_events_jsonl(path)


def test_recorded_jsonl_rejects_missing_fields(tmp_path: Path) -> None:
    path = tmp_path / "missing.jsonl"
    path.write_text('{"event_id": "1"}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="missing fields"):
        load_recorded_events_jsonl(path)
