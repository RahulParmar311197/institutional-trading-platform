import uuid
from decimal import Decimal

import pytest

from trading_platform.decision import decide
from trading_platform.oms import OrderManagementSystem, OrderState
from trading_platform.paper import PaperBroker
from trading_platform.risk import RiskDecisionType, RiskEngine, RiskLimits, build_approved_intent
from trading_platform.strategy import SignalDirection, StrategySignal


def signal(direction: SignalDirection = SignalDirection.LONG) -> StrategySignal:
    return StrategySignal(
        instrument_id=uuid.uuid4(),
        direction=direction,
        price=Decimal("100"),
        strategy_id="test_strategy",
        reason="test",
    )


def test_risk_rejects_order_above_limit() -> None:
    engine = RiskEngine(
        RiskLimits(
            max_order_notional=Decimal("500"),
            max_position_notional=Decimal("1000"),
        )
    )
    trading_decision = decide(signal())
    risk_decision = engine.evaluate(trading_decision, requested_quantity=6)
    assert risk_decision.decision is RiskDecisionType.REJECT
    assert risk_decision.reason == "MAX_ORDER_NOTIONAL"


def test_non_directional_decision_is_rejected() -> None:
    engine = RiskEngine(
        RiskLimits(
            max_order_notional=Decimal("1000"),
            max_position_notional=Decimal("1000"),
        )
    )
    trading_decision = decide(signal(SignalDirection.FLAT))
    risk_decision = engine.evaluate(trading_decision, requested_quantity=1)

    assert risk_decision.decision is RiskDecisionType.REJECT
    assert risk_decision.reason == "NO_DIRECTIONAL_DECISION"


def test_rejected_risk_cannot_create_order_intent() -> None:
    engine = RiskEngine(
        RiskLimits(
            max_order_notional=Decimal("50"),
            max_position_notional=Decimal("1000"),
        )
    )
    trading_decision = decide(signal())
    risk_decision = engine.evaluate(trading_decision, requested_quantity=1)
    with pytest.raises(ValueError, match="risk approval"):
        build_approved_intent(trading_decision, risk_decision)


def test_duplicate_fill_is_idempotent_and_does_not_duplicate_position() -> None:
    trading_signal = signal()
    trading_decision = decide(trading_signal)
    engine = RiskEngine(
        RiskLimits(
            max_order_notional=Decimal("1000"),
            max_position_notional=Decimal("2000"),
        )
    )
    risk_decision = engine.evaluate(trading_decision, requested_quantity=5)
    intent = build_approved_intent(trading_decision, risk_decision)

    oms = OrderManagementSystem()
    order = oms.create(intent)
    order.submit()

    broker = PaperBroker()
    broker.execute_market(order, fill_id="fill-1", price=Decimal("101"))
    broker.execute_market(order, fill_id="fill-1", price=Decimal("101"))

    assert order.state is OrderState.FILLED
    assert order.filled_quantity == 5
    position = broker.positions[trading_signal.instrument_id]
    assert position.quantity == 5
    assert position.average_price == Decimal("101")


def test_fill_cannot_exceed_order_quantity() -> None:
    trading_signal = signal()
    trading_decision = decide(trading_signal)
    engine = RiskEngine(
        RiskLimits(
            max_order_notional=Decimal("1000"),
            max_position_notional=Decimal("2000"),
        )
    )
    intent = build_approved_intent(
        trading_decision,
        engine.evaluate(trading_decision, requested_quantity=2),
    )
    order = OrderManagementSystem().create(intent)
    order.submit()

    with pytest.raises(ValueError, match="exceed"):
        order.apply_fill(fill_id="bad-fill", quantity=3)
