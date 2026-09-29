import uuid
from decimal import Decimal

from trading_platform.decision import decide
from trading_platform.journal import JournalEventType
from trading_platform.oms import OrderState
from trading_platform.paper import Position
from trading_platform.paper_engine import PaperTradingEngine
from trading_platform.reconciliation import reconcile_positions
from trading_platform.risk import RiskDecisionType, RiskEngine, RiskLimits
from trading_platform.strategy import SignalDirection, StrategySignal


def test_signal_to_paper_fill_position_and_reconciliation() -> None:
    instrument_id = uuid.uuid4()
    signal = StrategySignal(
        instrument_id=instrument_id,
        direction=SignalDirection.LONG,
        price=Decimal("100"),
        strategy_id="e2e_strategy",
        reason="validated_setup",
    )
    decision = decide(signal)
    engine = PaperTradingEngine(
        risk_engine=RiskEngine(
            RiskLimits(
                max_order_notional=Decimal("10000"),
                max_position_notional=Decimal("20000"),
            )
        )
    )

    result = engine.execute_market(
        decision,
        requested_quantity=10,
        fill_id="paper-fill-001",
        fill_price=Decimal("101"),
    )

    assert result.risk_decision.decision is RiskDecisionType.APPROVE
    assert result.order is not None
    assert result.order.state is OrderState.FILLED
    assert result.order.intent.decision_id == decision.id
    assert result.position is not None
    assert result.position.quantity == 10
    assert result.position.average_price == Decimal("101")

    expected = {
        instrument_id: Position(quantity=10, average_price=Decimal("101")),
    }
    reconciliation = reconcile_positions(expected, engine.broker.positions)
    assert reconciliation.matched is True

    journal_types = tuple(event.event_type for event in engine.journal.events)
    assert journal_types == (
        JournalEventType.DECISION,
        JournalEventType.RISK_APPROVED,
        JournalEventType.ORDER_CREATED,
        JournalEventType.ORDER_SUBMITTED,
        JournalEventType.FILL,
        JournalEventType.POSITION,
    )


def test_risk_rejection_stops_before_order_creation() -> None:
    signal = StrategySignal(
        instrument_id=uuid.uuid4(),
        direction=SignalDirection.LONG,
        price=Decimal("100"),
        strategy_id="e2e_strategy",
        reason="validated_setup",
    )
    decision = decide(signal)
    engine = PaperTradingEngine(
        risk_engine=RiskEngine(
            RiskLimits(
                max_order_notional=Decimal("50"),
                max_position_notional=Decimal("1000"),
            )
        )
    )

    result = engine.execute_market(
        decision,
        requested_quantity=1,
        fill_id="should-not-fill",
        fill_price=Decimal("100"),
    )

    assert result.risk_decision.decision is RiskDecisionType.REJECT
    assert result.order is None
    assert result.position is None
    assert engine.broker.positions == {}
    assert tuple(event.event_type for event in engine.journal.events) == (
        JournalEventType.DECISION,
        JournalEventType.RISK_REJECTED,
    )
