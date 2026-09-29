import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from trading_platform.oms import ManagedOrder
from trading_platform.trading_models import FillRecord, OrderRecord


class TradingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def persist_order(self, order: ManagedOrder) -> None:
        statement = insert(OrderRecord).values(
            id=order.id,
            intent_id=order.intent.id,
            decision_id=order.intent.decision_id,
            instrument_id=order.intent.instrument_id,
            strategy_id=order.intent.strategy_id,
            side=order.intent.direction.value,
            requested_quantity=order.intent.quantity,
            filled_quantity=order.filled_quantity,
            reference_price=order.intent.reference_price,
            state=order.state.value,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[OrderRecord.id],
            set_={
                "filled_quantity": order.filled_quantity,
                "state": order.state.value,
            },
        )
        await self.session.execute(statement)

    async def persist_fill(
        self,
        *,
        order_id: uuid.UUID,
        external_fill_id: str,
        source: str,
        quantity: int,
        price: Decimal,
        occurred_at: datetime,
    ) -> bool:
        if quantity <= 0 or price <= 0:
            raise ValueError("fill quantity and price must be positive")
        statement = (
            insert(FillRecord)
            .values(
                order_id=order_id,
                external_fill_id=external_fill_id,
                source=source,
                quantity=quantity,
                price=price,
                occurred_at=occurred_at,
            )
            .on_conflict_do_nothing(constraint="uq_fill_source_external_id")
            .returning(FillRecord.id)
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none() is not None
