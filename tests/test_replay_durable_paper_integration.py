import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from trading_platform.config import Settings
from trading_platform.durable_paper import DurablePaperTradingService
from trading_platform.infrastructure import Infrastructure
from trading_platform.instruments import Exchange, Instrument, Segment
from trading_platform.pipeline import ReplayStrategyPipeline
from trading_platform.recorded_events import RecordedEventType, RecordedMarketEvent
from trading_platform.risk import RiskEngine, RiskLimits
from trading_platform.strategy import EmaCrossoverStrategy
from trading_platform.trading_models import FillRecord, OrderRecord

pytestmark = pytest.mark.asyncio


def recorded_trade(
    instrument_id: uuid.UUID,
    *,
    event_id: str,
    minute: int,
    price: str,
) -> RecordedMarketEvent:
    timestamp = datetime(2026, 1, 1, 9, 15, tzinfo=UTC) + timedelta(minutes=minute)
    return RecordedMarketEvent(
        event_id=event_id,
        event_type=RecordedEventType.TRADE,
        instrument_id=instrument_id,
        source="integration-fixture",
        exchange_timestamp=timestamp,
        provider_timestamp=timestamp,
        ingestion_timestamp=timestamp,
        sequence=minute,
        price=Decimal(price),
        quantity=1,
    )


async def test_replay_decision_reaches_durable_paper_execution() -> None:
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
                    trading_symbol=f"REPLAY-{instrument_id.hex[:8]}",
                    name="Replay Integration Instrument",
                    lot_size=1,
                    tick_size=Decimal("0.05"),
                    active=True,
                )
            )
            await session.commit()

        pipeline = ReplayStrategyPipeline(
            instrument_id=instrument_id,
            interval=timedelta(minutes=1),
            strategy=EmaCrossoverStrategy(fast_period=1, slow_period=2),
        )
        steps = pipeline.run(
            [
                recorded_trade(instrument_id, event_id="4", minute=3, price="101"),
                recorded_trade(instrument_id, event_id="1", minute=0, price="100"),
                recorded_trade(instrument_id, event_id="3", minute=2, price="101"),
                recorded_trade(instrument_id, event_id="2", minute=1, price="99"),
            ]
        )
        directional = [
            step.decision
            for step in steps
            if step.decision is not None and step.decision.directional
        ]
        assert len(directional) == 1
        decision = directional[0]

        service = DurablePaperTradingService(
            sessions=infrastructure.sessions,
            risk_engine=RiskEngine(
                RiskLimits(
                    max_order_notional=Decimal("10000"),
                    max_position_notional=Decimal("20000"),
                )
            ),
        )
        result = await service.execute_market(
            decision,
            requested_quantity=2,
            fill_id="replay-integration-fill-001",
            fill_price=decision.reference_price,
        )

        assert result.order is not None
        assert result.position is not None
        assert result.position.quantity == 2

        async with infrastructure.sessions() as session:
            order_count = await session.scalar(
                select(func.count()).select_from(OrderRecord).where(
                    OrderRecord.instrument_id == instrument_id
                )
            )
            fill_count = await session.scalar(
                select(func.count()).select_from(FillRecord).where(
                    FillRecord.order_id == result.order.id
                )
            )
        assert order_count == 1
        assert fill_count == 1
    finally:
        await infrastructure.close()
