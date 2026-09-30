import os

import pytest

from trading_platform.config import Settings
from trading_platform.control_repository import RiskControlRepository
from trading_platform.controls import OperationalMode, RiskControlBook
from trading_platform.infrastructure import Infrastructure
from trading_platform.persistent_health import PersistentOperationalHealthGate
from trading_platform.system_health import SubsystemHealth

pytestmark = pytest.mark.asyncio


def healthy_statuses() -> dict[str, SubsystemHealth]:
    return {
        "database": SubsystemHealth.HEALTHY,
        "risk": SubsystemHealth.HEALTHY,
        "reconciliation": SubsystemHealth.HEALTHY,
        "market_data": SubsystemHealth.HEALTHY,
    }


async def test_health_escalation_persists_and_recovers_after_restart() -> None:
    if os.environ.get("ITP_RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("set ITP_RUN_INTEGRATION_TESTS=1 to run PostgreSQL integration tests")

    infrastructure = Infrastructure(Settings(_env_file=None))
    try:
        controls = RiskControlBook()
        statuses = healthy_statuses()
        statuses["database"] = SubsystemHealth.UNAVAILABLE

        decision = await PersistentOperationalHealthGate(
            sessions=infrastructure.sessions
        ).apply(controls, statuses)

        assert decision.mode is OperationalMode.HALTED
        assert controls.mode is OperationalMode.HALTED

        async with infrastructure.sessions() as session:
            recovered = await RiskControlRepository(session).load()
        assert recovered.mode is OperationalMode.HALTED
    finally:
        await infrastructure.close()


async def test_failed_persistence_keeps_restrictive_mode_in_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.environ.get("ITP_RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("set ITP_RUN_INTEGRATION_TESTS=1 to run PostgreSQL integration tests")

    infrastructure = Infrastructure(Settings(_env_file=None))
    try:
        controls = RiskControlBook()
        statuses = healthy_statuses()
        statuses["market_data"] = SubsystemHealth.DEGRADED

        async def fail_persist(*_: object, **__: object) -> None:
            raise RuntimeError("simulated control persistence failure")

        monkeypatch.setattr(RiskControlRepository, "persist_mode", fail_persist)

        with pytest.raises(RuntimeError, match="simulated control persistence failure"):
            await PersistentOperationalHealthGate(
                sessions=infrastructure.sessions
            ).apply(controls, statuses)

        assert controls.mode is OperationalMode.READ_ONLY
    finally:
        await infrastructure.close()


async def test_healthy_status_never_auto_relaxes_existing_restriction() -> None:
    if os.environ.get("ITP_RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("set ITP_RUN_INTEGRATION_TESTS=1 to run PostgreSQL integration tests")

    infrastructure = Infrastructure(Settings(_env_file=None))
    try:
        controls = RiskControlBook()
        controls.set_mode(OperationalMode.CLOSE_ONLY)

        decision = await PersistentOperationalHealthGate(
            sessions=infrastructure.sessions
        ).apply(controls, healthy_statuses())

        assert decision.mode is OperationalMode.NORMAL
        assert controls.mode is OperationalMode.CLOSE_ONLY
    finally:
        await infrastructure.close()
