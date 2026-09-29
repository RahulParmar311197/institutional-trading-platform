import uuid
from decimal import Decimal

from trading_platform.decision import DecisionAction, decide, to_signal
from trading_platform.strategy import SignalDirection, StrategySignal


def make_signal(direction: SignalDirection, price: str = "100") -> StrategySignal:
    return StrategySignal(
        instrument_id=uuid.uuid4(),
        direction=direction,
        price=Decimal(price),
        strategy_id="decision_test",
        reason="test",
    )


def test_long_signal_becomes_long_decision() -> None:
    signal = make_signal(SignalDirection.LONG)
    decision = decide(signal)

    assert decision.action is DecisionAction.LONG
    assert decision.directional is True
    assert to_signal(decision).direction is SignalDirection.LONG


def test_flat_signal_becomes_hold_decision() -> None:
    decision = decide(make_signal(SignalDirection.FLAT))

    assert decision.action is DecisionAction.HOLD
    assert decision.directional is False


def test_invalid_reference_price_fails_closed() -> None:
    decision = decide(make_signal(SignalDirection.LONG, price="0"))

    assert decision.action is DecisionAction.NO_TRADE
    assert decision.directional is False
    assert decision.reason == "INVALID_REFERENCE_PRICE"
