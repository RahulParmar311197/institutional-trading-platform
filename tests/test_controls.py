import uuid
from decimal import Decimal

from trading_platform.controls import (
    KillSwitchScope,
    OperationalMode,
    RiskControlBook,
    instrument_lock_key,
)
from trading_platform.decision import DecisionAction, TradingDecision
from trading_platform.risk import RiskDecisionType, RiskEngine, RiskLimits


def decision(*, action: DecisionAction = DecisionAction.LONG, strategy_id: str = "test") -> TradingDecision:
    return TradingDecision(
        id=uuid.uuid4(),
        instrument_id=uuid.uuid4(),
        action=action,
        reference_price=Decimal("100"),
        strategy_id=strategy_id,
        reason="test",
    )


def engine(controls: RiskControlBook) -> RiskEngine:
    return RiskEngine(
        RiskLimits(
            max_order_notional=Decimal("100000"),
            max_position_notional=Decimal("100000"),
        ),
        controls=controls,
    )


def test_global_kill_switch_blocks_directional_order() -> None:
    controls = RiskControlBook()
    controls.activate(KillSwitchScope.GLOBAL, reason="manual emergency stop")

    result = engine(controls).evaluate(decision(), requested_quantity=1)

    assert result.decision is RiskDecisionType.REJECT
    assert result.reason == "GLOBAL_KILL_SWITCH:manual emergency stop"


def test_account_strategy_and_instrument_locks_are_scoped() -> None:
    controls = RiskControlBook()
    target = decision(strategy_id="alpha-1")

    controls.activate(KillSwitchScope.ACCOUNT, key="acct-1", reason="account lock")
    assert engine(controls).evaluate(target, requested_quantity=1, account_id="acct-1").reason.startswith(
        "ACCOUNT_KILL_SWITCH"
    )
    assert engine(controls).evaluate(target, requested_quantity=1, account_id="acct-2").decision is RiskDecisionType.APPROVE

    controls.clear(KillSwitchScope.ACCOUNT, key="acct-1")
    controls.activate(KillSwitchScope.STRATEGY, key="alpha-1", reason="strategy lock")
    assert engine(controls).evaluate(target, requested_quantity=1).reason.startswith("STRATEGY_KILL_SWITCH")

    controls.clear(KillSwitchScope.STRATEGY, key="alpha-1")
    controls.activate(
        KillSwitchScope.INSTRUMENT,
        key=instrument_lock_key(target.instrument_id),
        reason="instrument lock",
    )
    assert engine(controls).evaluate(target, requested_quantity=1).reason.startswith("INSTRUMENT_KILL_SWITCH")


def test_read_only_and_halted_modes_block_new_directional_orders() -> None:
    controls = RiskControlBook()
    risk = engine(controls)

    controls.set_mode(OperationalMode.READ_ONLY)
    assert risk.evaluate(decision(), requested_quantity=1).reason == "OPERATIONAL_MODE_READ_ONLY"

    controls.set_mode(OperationalMode.HALTED)
    assert risk.evaluate(decision(), requested_quantity=1).reason == "OPERATIONAL_MODE_HALTED"


def test_close_only_allows_reduction_but_not_open_or_reversal() -> None:
    controls = RiskControlBook()
    controls.set_mode(OperationalMode.CLOSE_ONLY)
    risk = engine(controls)

    reduce_long = decision(action=DecisionAction.SHORT)
    approved = risk.evaluate(
        reduce_long,
        requested_quantity=3,
        current_position_quantity=10,
    )
    assert approved.decision is RiskDecisionType.APPROVE

    open_new = risk.evaluate(decision(), requested_quantity=1, current_position_quantity=0)
    assert open_new.reason == "OPERATIONAL_MODE_CLOSE_ONLY"

    reverse = risk.evaluate(
        reduce_long,
        requested_quantity=15,
        current_position_quantity=10,
    )
    assert reverse.reason == "OPERATIONAL_MODE_CLOSE_ONLY"
