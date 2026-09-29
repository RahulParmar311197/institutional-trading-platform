import os

import pytest

from trading_platform.config import Settings
from trading_platform.control_repository import RiskControlRepository
from trading_platform.controls import KillSwitchScope, OperationalMode, RiskLock
from trading_platform.infrastructure import Infrastructure

pytestmark = pytest.mark.asyncio


async def test_risk_controls_persist_and_recover() -> None:
    if os.environ.get("ITP_RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("set ITP_RUN_INTEGRATION_TESTS=1 to run PostgreSQL integration tests")

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
