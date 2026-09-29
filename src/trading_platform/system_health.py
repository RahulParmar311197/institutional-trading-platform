from dataclasses import dataclass
from enum import StrEnum

from trading_platform.controls import OperationalMode, RiskControlBook


class SubsystemHealth(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class HealthDecision:
    mode: OperationalMode
    reasons: tuple[str, ...]


class OperationalHealthGate:
    def __init__(
        self,
        *,
        required_subsystems: frozenset[str] | None = None,
        critical_subsystems: frozenset[str] | None = None,
    ) -> None:
        self.required_subsystems = required_subsystems or frozenset(
            {"database", "risk", "reconciliation", "market_data"}
        )
        self.critical_subsystems = critical_subsystems or frozenset(
            {"database", "risk", "reconciliation"}
        )
        if not self.critical_subsystems.issubset(self.required_subsystems):
            raise ValueError("critical_subsystems must be required_subsystems")

    def evaluate(self, statuses: dict[str, SubsystemHealth]) -> HealthDecision:
        missing = sorted(self.required_subsystems.difference(statuses))
        if missing:
            return HealthDecision(
                mode=OperationalMode.HALTED,
                reasons=tuple(f"MISSING_HEALTH:{name}" for name in missing),
            )

        critical_unavailable = sorted(
            name
            for name in self.critical_subsystems
            if statuses[name] is SubsystemHealth.UNAVAILABLE
        )
        if critical_unavailable:
            return HealthDecision(
                mode=OperationalMode.HALTED,
                reasons=tuple(
                    f"CRITICAL_UNAVAILABLE:{name}" for name in critical_unavailable
                ),
            )

        unavailable = sorted(
            name
            for name in self.required_subsystems
            if statuses[name] is SubsystemHealth.UNAVAILABLE
        )
        degraded = sorted(
            name
            for name in self.required_subsystems
            if statuses[name] is SubsystemHealth.DEGRADED
        )
        if unavailable or degraded:
            reasons = tuple(f"UNAVAILABLE:{name}" for name in unavailable) + tuple(
                f"DEGRADED:{name}" for name in degraded
            )
            return HealthDecision(mode=OperationalMode.READ_ONLY, reasons=reasons)

        return HealthDecision(mode=OperationalMode.NORMAL, reasons=())

    def apply(
        self,
        controls: RiskControlBook,
        statuses: dict[str, SubsystemHealth],
    ) -> HealthDecision:
        decision = self.evaluate(statuses)
        controls.set_mode(decision.mode)
        return decision
