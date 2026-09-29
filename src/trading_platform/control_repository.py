from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trading_platform.control_models import OperationalStateRecord, RiskLockRecord
from trading_platform.controls import KillSwitchScope, OperationalMode, RiskControlBook, RiskLock

GLOBAL_STORAGE_KEY = "*"
OPERATIONAL_STATE_ID = 1


class RiskControlRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _storage_key(lock: RiskLock) -> str:
        return GLOBAL_STORAGE_KEY if lock.key is None else lock.key

    @staticmethod
    def _domain_key(scope: KillSwitchScope, storage_key: str) -> str | None:
        if scope is KillSwitchScope.GLOBAL:
            return None
        return storage_key

    async def persist_lock(self, lock: RiskLock) -> None:
        storage_key = self._storage_key(lock)
        record = await self.session.get(
            RiskLockRecord,
            {"scope": lock.scope.value, "lock_key": storage_key},
        )
        if record is None:
            self.session.add(
                RiskLockRecord(
                    scope=lock.scope.value,
                    lock_key=storage_key,
                    reason=lock.reason,
                    active=True,
                )
            )
            return
        record.reason = lock.reason
        record.active = True

    async def clear_lock(
        self,
        scope: KillSwitchScope,
        *,
        key: str | None = None,
    ) -> bool:
        storage_key = GLOBAL_STORAGE_KEY if key is None else key
        record = await self.session.get(
            RiskLockRecord,
            {"scope": scope.value, "lock_key": storage_key},
        )
        if record is None or not record.active:
            return False
        record.active = False
        return True

    async def persist_mode(self, mode: OperationalMode) -> None:
        record = await self.session.get(OperationalStateRecord, OPERATIONAL_STATE_ID)
        if record is None:
            self.session.add(OperationalStateRecord(id=OPERATIONAL_STATE_ID, mode=mode.value))
            return
        record.mode = mode.value

    async def load(self) -> RiskControlBook:
        book = RiskControlBook()
        operational_state = await self.session.get(
            OperationalStateRecord,
            OPERATIONAL_STATE_ID,
        )
        if operational_state is not None:
            book.set_mode(OperationalMode(operational_state.mode))

        result = await self.session.scalars(
            select(RiskLockRecord).where(RiskLockRecord.active.is_(True))
        )
        for record in result:
            scope = KillSwitchScope(record.scope)
            book.activate(
                scope,
                key=self._domain_key(scope, record.lock_key),
                reason=record.reason,
            )
        return book
