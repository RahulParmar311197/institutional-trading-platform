import uuid
from decimal import Decimal

import pytest
from sqlalchemy.exc import OperationalError

from trading_platform.decision import decide
from trading_platform.durable_paper import DurablePaperTradingService
from trading_platform.risk import RiskDecisionType, RiskEngine, RiskLimits
from trading_platform.strategy import SignalDirection, StrategySignal

pytestmark = pytest.mark.asyncio


def unavailable_sessions() -> object:
    raise OperationalError(
        "connect",
        {},
        OSError("simulated database connection failure"),
    )


def make_decision(instrument_id: uuid.UUID):
    return decide(
        StrategySignal(
            instrument_id=instrument_id,
            direction=SignalDirection.LONG,
            price=Decimal("100"),
            strategy_id="database_failure_test",
            reason="verify_fail_closed_persistence",
        )
    )


async def test_approved_execution_does_not_publish_when_database_is_unavailable() -> None:
    instrument_id = uuid.uuid4()
    service = DurablePaperTradingService(
        sessions=unavailable_sessions,  # type: ignore[arg-type]
        risk_engine=RiskEngine(
            RiskLimits(
                max_order_notional=Decimal("10000"),
                max_position_notional=Decimal("20000"),
            )
        ),
    )

    with pytest.raises(OperationalError, match="simulated database connection failure"):
        await service.execute_market(
            make_decision(instrument_id),
            requested_quantity=2,
            fill_id="database-unavailable-fill",
            fill_price=Decimal("100"),
        )

    assert instrument_id not in service.broker.positions
    assert service.journal.events == ()


async def test_rejected_execution_does_not_publish_journal_when_database_is_unavailable() -> None:
    instrument_id = uuid.uuid4()
    service = DurablePaperTradingService(
        sessions=unavailable_sessions,  # type: ignore[arg-type]
        risk_engine=RiskEngine(
            RiskLimits(
                max_order_notional=Decimal("50"),
                max_position_notional=Decimal("20000"),
            )
        ),
    )
    decision = make_decision(instrument_id)
    expected_risk = service.risk_engine.evaluate(
        decision,
        requested_quantity=1,
        current_position_quantity=0,
    )
    assert expected_risk.decision is RiskDecisionType.REJECT

    with pytest.raises(OperationalError, match="simulated database connection failure"):
        await service.execute_market(
            decision,
            requested_quantity=1,
            fill_id="unused-rejected-fill",
            fill_price=Decimal("100"),
        )

    assert instrument_id not in service.broker.positions
    assert service.journal.events == ()
