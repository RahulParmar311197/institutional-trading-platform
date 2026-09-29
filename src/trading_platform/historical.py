import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from trading_platform.recorded_events import RecordedMarketEvent, normalize_recorded_events
from trading_platform.recorded_io import load_recorded_events_jsonl


class HistoricalEventSource(Protocol):
    def load(
        self,
        *,
        instrument_id: uuid.UUID | None = None,
    ) -> tuple[RecordedMarketEvent, ...]: ...


class JsonlRecordedEventSource:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(
        self,
        *,
        instrument_id: uuid.UUID | None = None,
    ) -> tuple[RecordedMarketEvent, ...]:
        events = load_recorded_events_jsonl(self.path)
        if instrument_id is None:
            return events
        return tuple(event for event in events if event.instrument_id == instrument_id)


def load_many(
    sources: Sequence[HistoricalEventSource],
    *,
    instrument_id: uuid.UUID | None = None,
) -> tuple[RecordedMarketEvent, ...]:
    events: list[RecordedMarketEvent] = []
    for source in sources:
        events.extend(source.load(instrument_id=instrument_id))
    return normalize_recorded_events(events)
