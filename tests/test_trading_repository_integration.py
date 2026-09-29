import os
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from trading_platform.config import Settings
from trading_platform.decision import decide
from trading_platform.infrastructure import Infrastructure
from trading_platform.instruments import Exchange, Instrument, Segment
from trading_platform.oms import OrderManagementSystem
from trading_platform.paper import PaperBroker
from trading_platform.risk import RiskEngine, RiskLimits, build_approved_intent
from trading_platform.strategy import SignalDirection, StrategySignal
from trading_platform.trading_models import FillRecord, OrderRecord
from trading_platform.trading_repository import TradingRepository

pytestmark = pytest.mark.asyncio


async def test_repository_persists_order_and_deduplicates_fill() -> None:
    if os.environ.get("ITP_RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("set ITP_RUN_INTEGRATION_TESTS=1 to run PostgreSQL integration tests")

    infrastructure = Infrastructure(Settings(_env_file=None))
    instrument_id = uuid.uuid4()
    try:
        async with infrastructure.sessions() as session:
            instrument = Instrument(
                id=instrument_id,
                exchange=Exchange.NSE,
                segment=Segment.CASH,
                trading_symbol=f"TEST-{instrument_id.hex[:8]}",
                name="Integration Test Instrument",
                lot_size=1,
                tick_size=Decimal("0.05"),
                active=True,
            )
            session.add(instrument)
            await session.commit()

            signal = StrategySignal(
                instrument_id=instrument_id,
                direction=SignalDirection.LONG,
                price=Decimal("100"),
                strategy_id="integration_strategy",
                reason="integration_test",
            )
            decision = decide(signal)
            risk_engine = RiskEngine(
                RiskLimits(
                    max_order_notional=Decimal("10000"),
                    max_position_notional=Decimal("20000"),
                )
            )
            risk_decision = risk_engine.evaluate(decision, requested_quantity=3)
            intent = build_approved_intent(decision, risk_decision)
            order = OrderManagementSystem().create(intent)
            order.submit()

            broker = PaperBroker()
            broker.execute_market(order, fill_id="db-fill-001", price=Decimal("101"))

            repository = TradingRepository(session)
            await repository.persist_order(order)
            inserted = await repository.persist_fill(
                order_id=order.id,
                external_fill_id="db-fill-001",
                source="paper",
                quantity=3,
                price=Decimal("101"),
                occurred_at=datetime.now(UTC),
            )
            duplicate = await repository.persist_fill(
                order_id=order.id,
                external_fill_id="db-fill-001",
                source="paper",
                quantity=3,
                price=Decimal("101"),
                occurred_at=datetime.now(UTC),
            )
            await session.commit()

            persisted_order = await session.get(OrderRecord, order.id)
            fill_count = await session.scalar(
                select(func.count()).select_from(FillRecord).where(FillRecord.order_id == order.id)
            )

            assert persisted_order is not None
            assert persisted_order.intent_id == intent.id
            assert persisted_order.decision_id == decision.id
            assert persisted_order.filled_quantity == 3
            assert persisted_order.state == "FILLED"
            assert inserted is True
            assert duplicate is False
            assert fill_count == 1
    finally:
        await infrastructure.close()
