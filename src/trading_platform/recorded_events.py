import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from trading_platform.candles import Trade


class RecordedEventType(StrEnum):
    TRADE = "TRADE"


@dataclass(frozen=True, slots=True)
class RecordedMarketEvent:
    event_id: str
    event_type: RecordedEventType
    instrument_id: uuid.UUID
    source: str
    exchange_timestamp: datetime
    provider_timestamp: datetime | None
    ingestion_timestamp: datetime
    sequence: int | None
    price: Decimal
    quantity: int

    def __post_init__(self) -> None:
        for field_name, timestamp in (
            ("exchange_timestamp", self.exchange_timestamp),
            ("ingestion_timestamp", self.ingestion_timestamp),
        ):
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError(f"{field_name} must be timezone-aware")
        if self.provider_timestamp is not None and (
            self.provider_timestamp.tzinfo is None
            or self.provider_timestamp.utcoffset() is None
        ):
            raise ValueError("provider_timestamp must be timezone-aware")
        if not self.event_id:
            raise ValueError("event_id must not be empty")
        if not self.source:
            raise ValueError("source must not be empty")
        if self.sequence is not None and self.sequence < 0:
            raise ValueError("sequence must be non-negative")
        if self.price <= 0:
            raise ValueError("price must be positive")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")

    def to_trade(self) -> Trade:
        if self.event_type is not RecordedEventType.TRADE:
            raise ValueError("event cannot be converted to a trade")
        return Trade(
            instrument_id=self.instrument_id,
            timestamp=self.exchange_timestamp,
            price=self.price,
            quantity=self.quantity,
        )


def normalize_recorded_events(
    events: list[RecordedMarketEvent],
) -> tuple[RecordedMarketEvent, ...]:
    unique: dict[tuple[str, str], RecordedMarketEvent] = {}
    for event in events:
        key = (event.source, event.event_id)
        existing = unique.get(key)
        if existing is not None and existing != event:
            raise ValueError(f"conflicting duplicate recorded event: {key}")
        unique[key] = event

    def sort_key(event: RecordedMarketEvent) -> tuple[datetime, int, datetime, str]:
        sequence = event.sequence if event.sequence is not None else 2**63 - 1
        return (
            event.exchange_timestamp,
            sequence,
            event.ingestion_timestamp,
            event.event_id,
        )

    return tuple(sorted(unique.values(), key=sort_key))
