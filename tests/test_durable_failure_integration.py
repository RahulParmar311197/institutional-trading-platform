import os
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from trading_platform.audit_repository import AuditRepository
from trading_platform.config import Settings
from trading_platform.decision import decide
from trading_platform.durable_paper import DurablePaperTradingService
from trading_platform.infrastructure import Infrastructure
from trading_platform.instruments import Exchange, Instrument, Segment
from trading_platform.risk import RiskEngine, RiskLimits
from trading_platform.strategy import SignalDirection, StrategySignal
from trading_platform.trading_models import FillRecord, OrderRecord

pytestmark = pytest.mark.asyncio


async def test_audit_failure_rolls_back_order_fill_and_in_memory_publish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
                    trading_symbol=f"ROLLBACK-{instrument_id.hex[:8]}",
                    name="Rollback Integration Instrument",
                    lot_size=1,
                    tick_size=Decimal("0.05"),
                    active=True,
                )
            )
            await session.commit()

        async def fail_audit(*_: object, **__: object) -> bool:
            raise RuntimeError("simulated audit persistence failure")

        monkeypatch.setattr(AuditRepository, "persist_journal_event", fail_audit)

        service = DurablePaperTradingService(
            sessions=infrastructure.sessions,
            risk_engine=RiskEngine(
                RiskLimits(
                    max_order_notional=Decimal("10000"),
                    max_position_notional=Decimal("20000"),
                )
            ),
        )
        decision = decide(
            StrategySignal(
                instrument_id=instrument_id,
                direction=SignalDirection.LONG,
                price=Decimal("100"),
                strategy_id="rollback_integration",
                reason="simulate_transaction_failure",
            )
        )

        with pytest.raises(RuntimeError, match="simulated audit persistence failure"):
            await service.execute_market(
                decision,
                requested_quantity=2,
                fill_id="rollback-fill-001",
                fill_price=Decimal("100"),
            )

        assert instrument_id not in service.broker.positions
        assert service.journal.events == ()

        async with infrastructure.sessions() as session:
            order_count = await session.scalar(
                select(func.count())
                .select_from(OrderRecord)
                .where(OrderRecord.instrument_id == instrument_id)
            )
            fill_count = await session.scalar(
                select(func.count())
                .select_from(FillRecord)
                .where(FillRecord.external_fill_id == "rollback-fill-001")
            )
        assert order_count == 0
        assert fill_count == 0
    finally:
        await infrastructure.close()
