from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from trading_platform.control_repository import RiskControlRepository
from trading_platform.controls import OperationalMode, RiskControlBook
from trading_platform.system_health import (
    HealthDecision,
    OperationalHealthGate,
    SubsystemHealth,
)

_MODE_RESTRICTION = {
    OperationalMode.NORMAL: 0,
    OperationalMode.CLOSE_ONLY: 1,
    OperationalMode.READ_ONLY: 2,
    OperationalMode.HALTED: 3,
}


class PersistentOperationalHealthGate:
    """Escalate operational safety from health state and persist before recovery.

    Health automation is intentionally escalation-only. A healthy status does not clear an
    operator-imposed or previously health-imposed restrictive mode; relaxing controls is an
    explicit operational action handled separately.
    """

    def __init__(
        self,
        *,
        sessions: async_sessionmaker[AsyncSession],
        gate: OperationalHealthGate | None = None,
    ) -> None:
        self.sessions = sessions
        self.gate = gate or OperationalHealthGate()

    async def apply(
        self,
        controls: RiskControlBook,
        statuses: dict[str, SubsystemHealth],
    ) -> HealthDecision:
        decision = self.gate.evaluate(statuses)
        if _MODE_RESTRICTION[decision.mode] <= _MODE_RESTRICTION[controls.mode]:
            return decision

        previous_mode = controls.mode
        controls.set_mode(decision.mode)
        try:
            async with self.sessions() as session, session.begin():
                await RiskControlRepository(session).persist_mode(decision.mode)
        except Exception:
            # Never relax after a failed attempt to persist a safer state. The running
            # process remains at the more restrictive health-driven mode.
            controls.set_mode(decision.mode)
            raise

        if _MODE_RESTRICTION[controls.mode] < _MODE_RESTRICTION[previous_mode]:
            raise RuntimeError("health gate unexpectedly relaxed operational controls")
        return decision
