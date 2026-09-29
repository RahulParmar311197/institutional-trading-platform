import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from trading_platform.audit_repository import AuditRepository
from trading_platform.decision import TradingDecision
from trading_platform.journal import ExecutionJournal, JournalEventType
from trading_platform.oms import ManagedOrder, OrderManagementSystem
from trading_platform.paper import PaperBroker, Position
from trading_platform.paper_engine import PaperExecutionResult
from trading_platform.risk import (
    RiskDecisionType,
    RiskEngine,
    build_approved_intent,
)
from trading_platform.trading_repository import TradingRepository


class DuplicateFillError(RuntimeError):
    pass


class DurablePaperTradingService:
    def __init__(
        self,
        *,
        sessions: async_sessionmaker[AsyncSession],
        risk_engine: RiskEngine,
        oms: OrderManagementSystem | None = None,
        broker: PaperBroker | None = None,
        journal: ExecutionJournal | None = None,
    ) -> None:
        self.sessions = sessions
        self.risk_engine = risk_engine
        self.oms = oms or OrderManagementSystem()
        self.broker = broker or PaperBroker()
        self.journal = journal or ExecutionJournal()

    async def execute_market(
        self,
        decision: TradingDecision,
        *,
        requested_quantity: int,
        fill_id: str,
        fill_price: Decimal,
    ) -> PaperExecutionResult:
        staged_journal = ExecutionJournal()
        staged_journal.append(
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
        staged_journal.append(
            risk_event_type,
            instrument_id=decision.instrument_id,
            decision_id=decision.id,
            details={
                "reason": risk_decision.reason,
                "approved_quantity": risk_decision.approved_quantity,
            },
        )

        if risk_decision.decision is not RiskDecisionType.APPROVE:
            await self._persist_journal(staged_journal)
            self.journal.extend(staged_journal.events)
            return PaperExecutionResult(risk_decision, None, None)

        intent = build_approved_intent(decision, risk_decision)
        staged_order = ManagedOrder(id=uuid.uuid4(), intent=intent)
        staged_order.submit()
        staged_journal.append(
            JournalEventType.ORDER_CREATED,
            instrument_id=decision.instrument_id,
            decision_id=decision.id,
            order_id=staged_order.id,
            details={"quantity": intent.quantity},
        )
        staged_journal.append(
            JournalEventType.ORDER_SUBMITTED,
            instrument_id=decision.instrument_id,
            decision_id=decision.id,
            order_id=staged_order.id,
        )

        staged_broker = PaperBroker()
        if decision.instrument_id in self.broker.positions:
            staged_broker.positions[decision.instrument_id] = Position(
                quantity=current_position.quantity,
                average_price=current_position.average_price,
                realized_pnl=current_position.realized_pnl,
            )
        staged_broker.execute_market(staged_order, fill_id=fill_id, price=fill_price)
        staged_position = staged_broker.positions[decision.instrument_id]
        staged_journal.append(
            JournalEventType.FILL,
            instrument_id=decision.instrument_id,
            decision_id=decision.id,
            order_id=staged_order.id,
            details={
                "fill_id": fill_id,
                "filled_quantity": staged_order.filled_quantity,
                "fill_price": str(fill_price),
            },
        )
        staged_journal.append(
            JournalEventType.POSITION,
            instrument_id=decision.instrument_id,
            decision_id=decision.id,
            order_id=staged_order.id,
            details={
                "quantity": staged_position.quantity,
                "average_price": str(staged_position.average_price),
                "realized_pnl": str(staged_position.realized_pnl),
            },
        )

        async with self.sessions() as session, session.begin():
            trading_repository = TradingRepository(session)
            await trading_repository.persist_order(staged_order)
            fill_inserted = await trading_repository.persist_fill(
                order_id=staged_order.id,
                external_fill_id=fill_id,
                source="paper",
                quantity=staged_order.filled_quantity,
                price=fill_price,
                occurred_at=staged_journal.events[-2].timestamp,
            )
            if not fill_inserted:
                raise DuplicateFillError(f"duplicate paper fill id: {fill_id}")

            audit_repository = AuditRepository(session)
            for event in staged_journal.events:
                await audit_repository.persist_journal_event(event)

        self.oms.register(staged_order)
        self.broker.positions[decision.instrument_id] = staged_position
        self.journal.extend(staged_journal.events)
        return PaperExecutionResult(risk_decision, staged_order, staged_position)

    async def _persist_journal(self, journal: ExecutionJournal) -> None:
        async with self.sessions() as session, session.begin():
            repository = AuditRepository(session)
            for event in journal.events:
                await repository.persist_journal_event(event)
