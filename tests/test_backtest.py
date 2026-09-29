import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from trading_platform.backtest import EventDrivenBacktester, ExecutionAssumptions
from trading_platform.config import Settings
from trading_platform.decision import DecisionAction
from trading_platform.recorded_events import RecordedEventType, RecordedMarketEvent
from trading_platform.risk import RiskEngine, RiskLimits
from trading_platform.strategy import EmaCrossoverStrategy

INSTRUMENT_ID = uuid.uuid4()
BASE = datetime(2026, 1, 1, 9, 15, tzinfo=UTC)


def event(event_id: str, minute: int, price: str) -> RecordedMarketEvent:
    timestamp = BASE + timedelta(minutes=minute)
    return RecordedMarketEvent(
        event_id=event_id,
        event_type=RecordedEventType.TRADE,
        instrument_id=INSTRUMENT_ID,
        source="backtest-fixture",
        exchange_timestamp=timestamp,
        provider_timestamp=timestamp,
        ingestion_timestamp=timestamp,
        sequence=minute,
        price=Decimal(price),
        quantity=1,
    )


def risk_engine(*, max_order: str = "100000") -> RiskEngine:
    return RiskEngine(
        RiskLimits(
            max_order_notional=Decimal(max_order),
            max_position_notional=Decimal("100000"),
        )
    )


def test_event_driven_backtest_is_repeatable_and_applies_fees() -> None:
    events = [
        event("5", 4, "98"),
        event("1", 0, "100"),
        event("3", 2, "101"),
        event("2", 1, "99"),
        event("4", 3, "98"),
    ]
    backtester = EventDrivenBacktester(
        interval=timedelta(minutes=1),
        strategy=EmaCrossoverStrategy(fast_period=1, slow_period=2),
        risk_engine=risk_engine(),
        requested_quantity=1,
        starting_equity=Decimal("10000"),
        assumptions=ExecutionAssumptions(fee_per_filled_order=Decimal("1")),
    )

    first = backtester.run(events)
    second = backtester.run(events)

    assert [trade.action for trade in first.trades] == [
        DecisionAction.LONG,
        DecisionAction.SHORT,
    ]
    assert [trade.fill_price for trade in first.trades] == [
        Decimal("101"),
        Decimal("98"),
    ]
    assert first.final_position_quantity == 0
    assert first.realized_pnl == Decimal("-3")
    assert first.unrealized_pnl == Decimal("0")
    assert first.total_fees == Decimal("2")
    assert first.net_pnl == Decimal("-5")
    assert first.final_equity == Decimal("9995")
    assert first == second


def test_backtest_slippage_moves_fill_against_trade_direction() -> None:
    assumptions = ExecutionAssumptions(slippage_bps=Decimal("10"))
    long_decision = next(
        step.decision
        for step in __import__("trading_platform.pipeline", fromlist=["ReplayStrategyPipeline"])
        .ReplayStrategyPipeline(
            instrument_id=INSTRUMENT_ID,
            interval=timedelta(minutes=1),
            strategy=EmaCrossoverStrategy(fast_period=1, slow_period=2),
        )
        .run([event("1", 0, "100"), event("2", 1, "99"), event("3", 2, "101"), event("4", 3, "101")])
        if step.decision is not None and step.decision.directional
    )

    assert long_decision is not None
    assert assumptions.fill_price(long_decision) == Decimal("101.101")


def test_risk_rejections_do_not_create_backtest_trades() -> None:
    backtester = EventDrivenBacktester(
        interval=timedelta(minutes=1),
        strategy=EmaCrossoverStrategy(fast_period=1, slow_period=2),
        risk_engine=risk_engine(max_order="50"),
        requested_quantity=1,
        starting_equity=Decimal("10000"),
    )
    result = backtester.run(
        [
            event("1", 0, "100"),
            event("2", 1, "99"),
            event("3", 2, "101"),
            event("4", 3, "98"),
            event("5", 4, "98"),
        ]
    )

    assert result.trades == ()
    assert result.rejected_decisions == 2
    assert result.net_pnl == Decimal("0")
    assert result.final_equity == Decimal("10000")
