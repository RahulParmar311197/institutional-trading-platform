from dataclasses import dataclass

from trading_platform.config import Environment, Settings
from trading_platform.controls import OperationalMode, RiskControlBook
from trading_platform.system_health import SubsystemHealth


@dataclass(frozen=True, slots=True)
class LiveTradingContext:
    explicit_user_approval: bool = False
    operator_authorized: bool = False
    broker_authenticated: bool = False
    reconciliation_complete: bool = False
    strategy_approved: bool = False
    capital_allocation_approved: bool = False
    kill_switch_operational: bool = False


@dataclass(frozen=True, slots=True)
class LiveGateDecision:
    allowed: bool
    reasons: tuple[str, ...]


def evaluate_live_trading_gate(
    settings: Settings,
    controls: RiskControlBook,
    health: dict[str, SubsystemHealth],
    context: LiveTradingContext,
) -> LiveGateDecision:
    reasons: list[str] = []

    if settings.environment is not Environment.LIVE:
        reasons.append("ENVIRONMENT_NOT_LIVE")
    if not settings.live_trading_enabled:
        reasons.append("LIVE_TRADING_DISABLED")
    if not context.explicit_user_approval:
        reasons.append("EXPLICIT_USER_APPROVAL_REQUIRED")
    if not context.operator_authorized:
        reasons.append("OPERATOR_AUTHORIZATION_REQUIRED")
    if not context.broker_authenticated:
        reasons.append("BROKER_NOT_AUTHENTICATED")
    if not context.reconciliation_complete:
        reasons.append("RECONCILIATION_INCOMPLETE")
    if not context.strategy_approved:
        reasons.append("STRATEGY_NOT_APPROVED")
    if not context.capital_allocation_approved:
        reasons.append("CAPITAL_ALLOCATION_NOT_APPROVED")
    if not context.kill_switch_operational:
        reasons.append("KILL_SWITCH_NOT_OPERATIONAL")
    if controls.mode is not OperationalMode.NORMAL:
        reasons.append(f"OPERATIONAL_MODE_{controls.mode.value}")
    if controls.locks:
        reasons.append("ACTIVE_RISK_LOCKS")

    required_health = ("database", "market_data", "risk", "audit", "reconciliation")
    for subsystem in required_health:
        status = health.get(subsystem)
        if status is None:
            reasons.append(f"MISSING_HEALTH:{subsystem}")
        elif status is not SubsystemHealth.HEALTHY:
            reasons.append(f"UNHEALTHY:{subsystem}:{status.value}")

    return LiveGateDecision(allowed=not reasons, reasons=tuple(reasons))
