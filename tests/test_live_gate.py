from trading_platform.config import Environment, Settings
from trading_platform.controls import KillSwitchScope, OperationalMode, RiskControlBook
from trading_platform.live_gate import LiveTradingContext, evaluate_live_trading_gate
from trading_platform.system_health import SubsystemHealth


def healthy() -> dict[str, SubsystemHealth]:
    return {
        "database": SubsystemHealth.HEALTHY,
        "market_data": SubsystemHealth.HEALTHY,
        "risk": SubsystemHealth.HEALTHY,
        "audit": SubsystemHealth.HEALTHY,
        "reconciliation": SubsystemHealth.HEALTHY,
    }


def approved_context() -> LiveTradingContext:
    return LiveTradingContext(
        explicit_user_approval=True,
        operator_authorized=True,
        broker_authenticated=True,
        reconciliation_complete=True,
        strategy_approved=True,
        capital_allocation_approved=True,
        kill_switch_operational=True,
    )


def live_settings() -> Settings:
    return Settings(
        _env_file=None,
        environment=Environment.LIVE,
        live_trading_enabled=True,
    )


def test_default_configuration_denies_live_trading() -> None:
    decision = evaluate_live_trading_gate(
        Settings(_env_file=None),
        RiskControlBook(),
        {},
        LiveTradingContext(),
    )

    assert decision.allowed is False
    assert "ENVIRONMENT_NOT_LIVE" in decision.reasons
    assert "LIVE_TRADING_DISABLED" in decision.reasons
    assert "EXPLICIT_USER_APPROVAL_REQUIRED" in decision.reasons


def test_all_explicit_gates_are_required_before_policy_allows() -> None:
    decision = evaluate_live_trading_gate(
        live_settings(),
        RiskControlBook(),
        healthy(),
        approved_context(),
    )

    assert decision.allowed is True
    assert decision.reasons == ()


def test_active_lock_or_non_normal_mode_denies_even_when_other_gates_pass() -> None:
    controls = RiskControlBook()
    controls.activate(KillSwitchScope.GLOBAL, reason="manual stop")
    locked = evaluate_live_trading_gate(
        live_settings(),
        controls,
        healthy(),
        approved_context(),
    )
    assert locked.allowed is False
    assert "ACTIVE_RISK_LOCKS" in locked.reasons

    controls.clear(KillSwitchScope.GLOBAL)
    controls.set_mode(OperationalMode.CLOSE_ONLY)
    close_only = evaluate_live_trading_gate(
        live_settings(),
        controls,
        healthy(),
        approved_context(),
    )
    assert close_only.allowed is False
    assert "OPERATIONAL_MODE_CLOSE_ONLY" in close_only.reasons


def test_unhealthy_or_missing_subsystem_denies_live_trading() -> None:
    health = healthy()
    health["market_data"] = SubsystemHealth.DEGRADED
    del health["audit"]

    decision = evaluate_live_trading_gate(
        live_settings(),
        RiskControlBook(),
        health,
        approved_context(),
    )

    assert decision.allowed is False
    assert "UNHEALTHY:market_data:DEGRADED" in decision.reasons
    assert "MISSING_HEALTH:audit" in decision.reasons
