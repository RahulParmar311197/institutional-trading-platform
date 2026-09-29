import uuid
from decimal import Decimal

import pytest

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
    decision = engine.evaluate(signal(), requested_quantity=6)
    assert decision.decision is RiskDecisionType.REJECT
    assert decision.reason == "MAX_ORDER_NOTIONAL"


def test_rejected_risk_cannot_create_order_intent() -> None:
    engine = RiskEngine(
        RiskLimits(
            max_order_notional=Decimal("50"),
            max_position_notional=Decimal("1000"),
        )
    )
    decision = engine.evaluate(signal(), requested_quantity=1)
    with pytest.raises(ValueError, match="risk approval"):
        build_approved_intent(signal(), decision)


def test_duplicate_fill_is_idempotent_and_does_not_duplicate_position() -> None:
    trading_signal = signal()
    engine = RiskEngine(
        RiskLimits(
            max_order_notional=Decimal("1000"),
            max_position_notional=Decimal("2000"),
        )
    )
    decision = engine.evaluate(trading_signal, requested_quantity=5)
    intent = build_approved_intent(trading_signal, decision)

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
    engine = RiskEngine(
        RiskLimits(
            max_order_notional=Decimal("1000"),
            max_position_notional=Decimal("2000"),
        )
    )
    intent = build_approved_intent(
        trading_signal,
        engine.evaluate(trading_signal, requested_quantity=2),
    )
    order = OrderManagementSystem().create(intent)
    order.submit()

    with pytest.raises(ValueError, match="exceed"):
        order.apply_fill(fill_id="bad-fill", quantity=3)
