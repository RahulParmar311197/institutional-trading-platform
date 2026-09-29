import os
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from trading_platform.config import Settings
from trading_platform.decision import decide
from trading_platform.durable_paper import DuplicateFillError, DurablePaperTradingService
from trading_platform.infrastructure import Infrastructure
from trading_platform.instruments import Exchange, Instrument, Segment
from trading_platform.models import AuditEvent
from trading_platform.risk import RiskEngine, RiskLimits
from trading_platform.strategy import SignalDirection, StrategySignal
from trading_platform.trading_models import FillRecord, OrderRecord

pytestmark = pytest.mark.asyncio


async def test_durable_execution_commits_before_publishing_and_rejects_duplicate_fill() -> None:
    if os.environ.get("ITP_RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("set ITP_RUN_INTEGRATION_TESTS=1 to run PostgreSQL integration tests")

    infrastructure = Infrastructure(Settings(_env_file=None))
    instrument_id = uuid.uuid4()
    try:
        async with infrastructure.sessions() as session:
            session.add(
                Instrument(
                    id=instrument_id,
                    exchange=Exchange.NSE,
                    segment=Segment.CASH,
                    trading_symbol=f"DURABLE-{instrument_id.hex[:8]}",
                    name="Durable Paper Test Instrument",
                    lot_size=1,
                    tick_size=Decimal("0.05"),
                    active=True,
                )
            )
            await session.commit()

        service = DurablePaperTradingService(
            sessions=infrastructure.sessions,
            risk_engine=RiskEngine(
                RiskLimits(
                    max_order_notional=Decimal("10000"),
                    max_position_notional=Decimal("20000"),
                )
            ),
        )
        first_decision = decide(
            StrategySignal(
                instrument_id=instrument_id,
                direction=SignalDirection.LONG,
                price=Decimal("100"),
                strategy_id="durable_integration",
                reason="integration_test",
            )
        )

        result = await service.execute_market(
            first_decision,
            requested_quantity=4,
            fill_id="durable-fill-001",
            fill_price=Decimal("101"),
        )

        assert result.order is not None
        assert result.position is not None
        assert result.position.quantity == 4
        assert service.oms.get(result.order.id) is result.order
        assert len(service.journal.events) == 6

        async with infrastructure.sessions() as session:
            order_count = await session.scalar(select(func.count()).select_from(OrderRecord))
            fill_count = await session.scalar(select(func.count()).select_from(FillRecord))
            audit_count = await session.scalar(select(func.count()).select_from(AuditEvent))
            assert order_count == 1
            assert fill_count == 1
            assert audit_count == 6

        second_decision = decide(
            StrategySignal(
                instrument_id=instrument_id,
                direction=SignalDirection.LONG,
                price=Decimal("100"),
                strategy_id="durable_integration",
                reason="duplicate_fill_attempt",
            )
        )
        with pytest.raises(DuplicateFillError):
            await service.execute_market(
                second_decision,
                requested_quantity=1,
                fill_id="durable-fill-001",
                fill_price=Decimal("102"),
            )

        assert service.broker.positions[instrument_id].quantity == 4
        assert len(service.journal.events) == 6
        async with infrastructure.sessions() as session:
            order_count = await session.scalar(select(func.count()).select_from(OrderRecord))
            fill_count = await session.scalar(select(func.count()).select_from(FillRecord))
            audit_count = await session.scalar(select(func.count()).select_from(AuditEvent))
            assert order_count == 1
            assert fill_count == 1
            assert audit_count == 6
    finally:
        await infrastructure.close()
