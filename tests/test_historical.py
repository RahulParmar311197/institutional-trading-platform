import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from trading_platform.historical import JsonlRecordedEventSource, load_many
from trading_platform.recorded_events import RecordedEventType, RecordedMarketEvent
from trading_platform.recorded_io import write_recorded_events_jsonl


def event(
    instrument_id: uuid.UUID,
    *,
    event_id: str,
    minute: int,
) -> RecordedMarketEvent:
    timestamp = datetime(2026, 1, 1, 9, 15, tzinfo=UTC) + timedelta(minutes=minute)
    return RecordedMarketEvent(
        event_id=event_id,
        event_type=RecordedEventType.TRADE,
        instrument_id=instrument_id,
        source="historical-fixture",
        exchange_timestamp=timestamp,
        provider_timestamp=timestamp,
        ingestion_timestamp=timestamp,
        sequence=minute,
        price=Decimal("100") + Decimal(minute),
        quantity=1,
    )


def test_jsonl_historical_source_filters_by_instrument(tmp_path: Path) -> None:
    first = uuid.uuid4()
    second = uuid.uuid4()
    path = tmp_path / "events.jsonl"
    write_recorded_events_jsonl(
        path,
        [event(first, event_id="1", minute=0), event(second, event_id="2", minute=1)],
    )

    source = JsonlRecordedEventSource(path)

    assert len(source.load()) == 2
    filtered = source.load(instrument_id=first)
    assert len(filtered) == 1
    assert filtered[0].instrument_id == first


def test_load_many_normalizes_events_across_sources(tmp_path: Path) -> None:
    instrument_id = uuid.uuid4()
    first_path = tmp_path / "first.jsonl"
    second_path = tmp_path / "second.jsonl"
    write_recorded_events_jsonl(
        first_path,
        [event(instrument_id, event_id="2", minute=1)],
    )
    write_recorded_events_jsonl(
        second_path,
        [event(instrument_id, event_id="1", minute=0)],
    )

    loaded = load_many(
        [JsonlRecordedEventSource(first_path), JsonlRecordedEventSource(second_path)]
    )

    assert [item.event_id for item in loaded] == ["1", "2"]
