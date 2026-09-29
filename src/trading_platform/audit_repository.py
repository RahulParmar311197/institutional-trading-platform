from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from trading_platform.journal import JournalEvent
from trading_platform.models import AuditEvent


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def persist_journal_event(
        self,
        event: JournalEvent,
        *,
        actor: str = "system:paper-engine",
    ) -> bool:
        payload = {
            "instrument_id": str(event.instrument_id),
            "decision_id": str(event.decision_id) if event.decision_id is not None else None,
            "order_id": str(event.order_id) if event.order_id is not None else None,
            "details": event.details,
        }
        statement = (
            insert(AuditEvent)
            .values(
                id=event.id,
                event_type=f"paper.{event.event_type.value.lower()}",
                actor=actor,
                payload=payload,
                occurred_at=event.timestamp,
            )
            .on_conflict_do_nothing(index_elements=[AuditEvent.id])
            .returning(AuditEvent.id)
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none() is not None
