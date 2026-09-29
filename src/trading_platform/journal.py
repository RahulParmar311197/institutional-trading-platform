import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class JournalEventType(StrEnum):
    DECISION = "DECISION"
    RISK_APPROVED = "RISK_APPROVED"
    RISK_REJECTED = "RISK_REJECTED"
    ORDER_CREATED = "ORDER_CREATED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    FILL = "FILL"
    POSITION = "POSITION"
    RECONCILIATION = "RECONCILIATION"


@dataclass(frozen=True, slots=True)
class JournalEvent:
    id: uuid.UUID
    event_type: JournalEventType
    timestamp: datetime
    instrument_id: uuid.UUID
    decision_id: uuid.UUID | None
    order_id: uuid.UUID | None
    details: dict[str, Any]


@dataclass(slots=True)
class ExecutionJournal:
    _events: list[JournalEvent] = field(default_factory=list)

    def append(
        self,
        event_type: JournalEventType,
        *,
        instrument_id: uuid.UUID,
        decision_id: uuid.UUID | None = None,
        order_id: uuid.UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> JournalEvent:
        event = JournalEvent(
            id=uuid.uuid4(),
            event_type=event_type,
            timestamp=datetime.now(UTC),
            instrument_id=instrument_id,
            decision_id=decision_id,
            order_id=order_id,
            details=dict(details or {}),
        )
        self._events.append(event)
        return event

    def extend(self, events: Iterable[JournalEvent]) -> None:
        self._events.extend(events)

    @property
    def events(self) -> tuple[JournalEvent, ...]:
        return tuple(self._events)
