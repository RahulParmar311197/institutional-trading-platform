import json
from pathlib import Path
from typing import Any
from uuid import UUID

from trading_platform.recorded_events import (
    RecordedEventType,
    RecordedMarketEvent,
    normalize_recorded_events,
)


def recorded_event_to_dict(event: RecordedMarketEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "event_type": event.event_type.value,
        "instrument_id": str(event.instrument_id),
        "source": event.source,
        "exchange_timestamp": event.exchange_timestamp.isoformat(),
        "provider_timestamp": (
            event.provider_timestamp.isoformat()
            if event.provider_timestamp is not None
            else None
        ),
        "ingestion_timestamp": event.ingestion_timestamp.isoformat(),
        "sequence": event.sequence,
        "price": str(event.price),
        "quantity": event.quantity,
    }


def recorded_event_from_dict(payload: dict[str, Any]) -> RecordedMarketEvent:
    from datetime import datetime
    from decimal import Decimal

    required = {
        "event_id",
        "event_type",
        "instrument_id",
        "source",
        "exchange_timestamp",
        "provider_timestamp",
        "ingestion_timestamp",
        "sequence",
        "price",
        "quantity",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise ValueError(f"recorded event missing fields: {', '.join(missing)}")

    provider_timestamp_raw = payload["provider_timestamp"]
    provider_timestamp = (
        datetime.fromisoformat(str(provider_timestamp_raw))
        if provider_timestamp_raw is not None
        else None
    )
    return RecordedMarketEvent(
        event_id=str(payload["event_id"]),
        event_type=RecordedEventType(str(payload["event_type"])),
        instrument_id=UUID(str(payload["instrument_id"])),
        source=str(payload["source"]),
        exchange_timestamp=datetime.fromisoformat(str(payload["exchange_timestamp"])),
        provider_timestamp=provider_timestamp,
        ingestion_timestamp=datetime.fromisoformat(str(payload["ingestion_timestamp"])),
        sequence=(
            int(payload["sequence"]) if payload["sequence"] is not None else None
        ),
        price=Decimal(str(payload["price"])),
        quantity=int(payload["quantity"]),
    )


def load_recorded_events_jsonl(path: Path) -> tuple[RecordedMarketEvent, ...]:
    events: list[RecordedMarketEvent] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at line {line_number}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"recorded event line {line_number} must be a JSON object")
            events.append(recorded_event_from_dict(payload))
    return normalize_recorded_events(events)


def write_recorded_events_jsonl(
    path: Path,
    events: list[RecordedMarketEvent],
) -> None:
    normalized = normalize_recorded_events(events)
    with path.open("w", encoding="utf-8") as handle:
        for event in normalized:
            handle.write(json.dumps(recorded_event_to_dict(event), sort_keys=True))
            handle.write("\n")
