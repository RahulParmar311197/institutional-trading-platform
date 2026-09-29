from trading_platform.controls import OperationalMode, RiskControlBook
from trading_platform.system_health import OperationalHealthGate, SubsystemHealth


def healthy_statuses() -> dict[str, SubsystemHealth]:
    return {
        "database": SubsystemHealth.HEALTHY,
        "risk": SubsystemHealth.HEALTHY,
        "reconciliation": SubsystemHealth.HEALTHY,
        "market_data": SubsystemHealth.HEALTHY,
    }


def test_all_required_subsystems_healthy_allows_normal_mode() -> None:
    decision = OperationalHealthGate().evaluate(healthy_statuses())

    assert decision.mode is OperationalMode.NORMAL
    assert decision.reasons == ()


def test_missing_required_health_fails_closed_to_halted() -> None:
    statuses = healthy_statuses()
    del statuses["risk"]

    decision = OperationalHealthGate().evaluate(statuses)

    assert decision.mode is OperationalMode.HALTED
    assert decision.reasons == ("MISSING_HEALTH:risk",)


def test_critical_unavailable_health_halts() -> None:
    statuses = healthy_statuses()
    statuses["database"] = SubsystemHealth.UNAVAILABLE

    decision = OperationalHealthGate().evaluate(statuses)

    assert decision.mode is OperationalMode.HALTED
    assert decision.reasons == ("CRITICAL_UNAVAILABLE:database",)


def test_degraded_or_noncritical_unavailable_health_is_read_only() -> None:
    statuses = healthy_statuses()
    statuses["market_data"] = SubsystemHealth.DEGRADED

    decision = OperationalHealthGate().evaluate(statuses)

    assert decision.mode is OperationalMode.READ_ONLY
    assert decision.reasons == ("DEGRADED:market_data",)


def test_health_gate_applies_mode_to_risk_controls() -> None:
    controls = RiskControlBook()
    statuses = healthy_statuses()
    statuses["market_data"] = SubsystemHealth.UNAVAILABLE

    decision = OperationalHealthGate().apply(controls, statuses)

    assert decision.mode is OperationalMode.READ_ONLY
    assert controls.mode is OperationalMode.READ_ONLY
