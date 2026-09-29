import os
import uuid

import pytest
from sqlalchemy import func, select

from trading_platform.audit_repository import AuditRepository
from trading_platform.config import Settings
from trading_platform.infrastructure import Infrastructure
from trading_platform.journal import ExecutionJournal, JournalEventType
from trading_platform.models import AuditEvent

pytestmark = pytest.mark.asyncio


async def test_journal_event_is_persisted_once() -> None:
    if os.environ.get("ITP_RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("set ITP_RUN_INTEGRATION_TESTS=1 to run PostgreSQL integration tests")

    infrastructure = Infrastructure(Settings(_env_file=None))
    try:
        journal = ExecutionJournal()
        event = journal.append(
            JournalEventType.DECISION,
            instrument_id=uuid.uuid4(),
            decision_id=uuid.uuid4(),
            details={"action": "LONG", "reason": "integration_test"},
        )

        async with infrastructure.sessions() as session:
            repository = AuditRepository(session)
            inserted = await repository.persist_journal_event(event)
            duplicate = await repository.persist_journal_event(event)
            await session.commit()

            count = await session.scalar(
                select(func.count()).select_from(AuditEvent).where(AuditEvent.id == event.id)
            )
            persisted = await session.get(AuditEvent, event.id)

            assert inserted is True
            assert duplicate is False
            assert count == 1
            assert persisted is not None
            assert persisted.event_type == "paper.decision"
            assert persisted.payload["decision_id"] == str(event.decision_id)
    finally:
        await infrastructure.close()
