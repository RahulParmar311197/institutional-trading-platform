import os

import pytest

from trading_platform.config import Settings
from trading_platform.control_models import OperationalStateRecord, RiskLockRecord
from trading_platform.control_repository import (
    OPERATIONAL_STATE_ID,
    RiskControlRepository,
)
from trading_platform.controls import KillSwitchScope, OperationalMode, RiskLock
from trading_platform.infrastructure import Infrastructure

pytestmark = pytest.mark.asyncio


def require_integration_tests() -> None:
    if os.environ.get("ITP_RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("set ITP_RUN_INTEGRATION_TESTS=1 to run PostgreSQL integration tests")


async def test_risk_controls_persist_and_recover() -> None:
    require_integration_tests()

    infrastructure = Infrastructure(Settings(_env_file=None))
    try:
        async with infrastructure.sessions() as session:
            repository = RiskControlRepository(session)
            await repository.persist_mode(OperationalMode.CLOSE_ONLY)
            await repository.persist_lock(
                RiskLock(
                    scope=KillSwitchScope.GLOBAL,
                    key=None,
                    reason="integration emergency stop",
                )
            )
            await session.commit()

        async with infrastructure.sessions() as recovery_session:
            repository = RiskControlRepository(recovery_session)
            recovered = await repository.load()
            assert recovered.mode is OperationalMode.CLOSE_ONLY
            assert len(recovered.locks) == 1
            assert recovered.locks[0].scope is KillSwitchScope.GLOBAL
            assert recovered.locks[0].reason == "integration emergency stop"

            cleared = await repository.clear_lock(KillSwitchScope.GLOBAL)
            assert cleared is True
            await repository.persist_mode(OperationalMode.HALTED)
            await recovery_session.commit()

        async with infrastructure.sessions() as final_session:
            final = await RiskControlRepository(final_session).load()
            assert final.mode is OperationalMode.HALTED
            assert final.locks == ()
    finally:
        await infrastructure.close()


async def test_missing_operational_state_fails_closed_after_migration_initialization() -> None:
    require_integration_tests()

    infrastructure = Infrastructure(Settings(_env_file=None))
    try:
        async with infrastructure.sessions() as session:
            record = await session.get(OperationalStateRecord, OPERATIONAL_STATE_ID)
            assert record is not None
            await session.delete(record)
            await session.flush()

            repository = RiskControlRepository(session)
            with pytest.raises(RuntimeError, match="operational state is missing"):
                await repository.load()
            with pytest.raises(RuntimeError, match="operational state is missing"):
                await repository.persist_mode(OperationalMode.NORMAL)

            await session.rollback()
    finally:
        await infrastructure.close()


async def test_corrupt_persisted_global_lock_storage_key_fails_closed() -> None:
    require_integration_tests()

    infrastructure = Infrastructure(Settings(_env_file=None))
    try:
        async with infrastructure.sessions() as session:
            session.add(
                RiskLockRecord(
                    scope=KillSwitchScope.GLOBAL.value,
                    lock_key="corrupt-global-key",
                    reason="corrupt fixture",
                    active=True,
                )
            )
            await session.flush()

            with pytest.raises(ValueError, match="global risk lock"):
                await RiskControlRepository(session).load()

            await session.rollback()
    finally:
        await infrastructure.close()


async def test_corrupt_persisted_non_global_sentinel_key_fails_closed() -> None:
    require_integration_tests()

    infrastructure = Infrastructure(Settings(_env_file=None))
    try:
        async with infrastructure.sessions() as session:
            session.add(
                RiskLockRecord(
                    scope=KillSwitchScope.STRATEGY.value,
                    lock_key="*",
                    reason="corrupt fixture",
                    active=True,
                )
            )
            await session.flush()

            with pytest.raises(ValueError, match="non-global risk lock"):
                await RiskControlRepository(session).load()

            await session.rollback()
    finally:
        await infrastructure.close()
