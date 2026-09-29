from dataclasses import dataclass
from decimal import Decimal

from trading_platform.decision import TradingDecision
from trading_platform.journal import ExecutionJournal, JournalEventType
from trading_platform.oms import ManagedOrder, OrderManagementSystem
from trading_platform.paper import PaperBroker, Position
from trading_platform.risk import (
    RiskDecision,
    RiskDecisionType,
    RiskEngine,
    build_approved_intent,
)


@dataclass(frozen=True, slots=True)
class PaperExecutionResult:
    risk_decision: RiskDecision
    order: ManagedOrder | None
    position: Position | None


class PaperTradingEngine:
    def __init__(
        self,
        *,
        risk_engine: RiskEngine,
        oms: OrderManagementSystem | None = None,
        broker: PaperBroker | None = None,
        journal: ExecutionJournal | None = None,
    ) -> None:
        self.risk_engine = risk_engine
        self.oms = oms or OrderManagementSystem()
        self.broker = broker or PaperBroker()
        self.journal = journal or ExecutionJournal()

    def execute_market(
        self,
        decision: TradingDecision,
        *,
        requested_quantity: int,
        fill_id: str,
        fill_price: Decimal,
    ) -> PaperExecutionResult:
        self.journal.append(
            JournalEventType.DECISION,
            instrument_id=decision.instrument_id,
            decision_id=decision.id,
            details={"action": decision.action.value, "reason": decision.reason},
        )

        current_position = self.broker.positions.get(decision.instrument_id, Position())
        risk_decision = self.risk_engine.evaluate(
            decision,
            requested_quantity=requested_quantity,
            current_position_quantity=current_position.quantity,
        )
        risk_event_type = (
            JournalEventType.RISK_APPROVED
            if risk_decision.decision is RiskDecisionType.APPROVE
            else JournalEventType.RISK_REJECTED
        )
        self.journal.append(
            risk_event_type,
            instrument_id=decision.instrument_id,
            decision_id=decision.id,
            details={
                "reason": risk_decision.reason,
                "approved_quantity": risk_decision.approved_quantity,
            },
        )

        if risk_decision.decision is not RiskDecisionType.APPROVE:
            return PaperExecutionResult(risk_decision=risk_decision, order=None, position=None)

        intent = build_approved_intent(decision, risk_decision)
        order = self.oms.create(intent)
        self.journal.append(
            JournalEventType.ORDER_CREATED,
            instrument_id=decision.instrument_id,
            decision_id=decision.id,
            order_id=order.id,
            details={"quantity": intent.quantity},
        )
        order.submit()
        self.journal.append(
            JournalEventType.ORDER_SUBMITTED,
            instrument_id=decision.instrument_id,
            decision_id=decision.id,
            order_id=order.id,
        )

        self.broker.execute_market(order, fill_id=fill_id, price=fill_price)
        self.journal.append(
            JournalEventType.FILL,
            instrument_id=decision.instrument_id,
            decision_id=decision.id,
            order_id=order.id,
            details={
                "fill_id": fill_id,
                "filled_quantity": order.filled_quantity,
                "fill_price": str(fill_price),
            },
        )
        position = self.broker.positions[decision.instrument_id]
        self.journal.append(
            JournalEventType.POSITION,
            instrument_id=decision.instrument_id,
            decision_id=decision.id,
            order_id=order.id,
            details={
                "quantity": position.quantity,
                "average_price": str(position.average_price),
                "realized_pnl": str(position.realized_pnl),
            },
        )
        return PaperExecutionResult(
            risk_decision=risk_decision,
            order=order,
            position=position,
        )
