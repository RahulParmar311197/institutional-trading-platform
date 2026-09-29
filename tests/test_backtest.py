import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trading_platform.backtest import EventDrivenBacktester, ExecutionAssumptions
from trading_platform.decision import DecisionAction
from trading_platform.pipeline import ReplayStrategyPipeline
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


def make_backtester(*, max_order: str = "100000") -> EventDrivenBacktester:
    return EventDrivenBacktester(
        interval=timedelta(minutes=1),
        strategy=EmaCrossoverStrategy(fast_period=1, slow_period=2),
        risk_engine=risk_engine(max_order=max_order),
        requested_quantity=1,
        starting_equity=Decimal("10000"),
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
    assert [trade.realized_pnl_delta for trade in first.trades] == [
        Decimal("0"),
        Decimal("-3"),
    ]
    assert [point.equity for point in first.equity_curve] == [
        Decimal("10000"),
        Decimal("10000"),
        Decimal("10000"),
        Decimal("9996"),
        Decimal("9995"),
    ]
    assert first.metrics.trade_count == 2
    assert first.metrics.winning_realizations == 0
    assert first.metrics.losing_realizations == 1
    assert first.metrics.gross_profit == Decimal("0")
    assert first.metrics.gross_loss == Decimal("3")
    assert first.metrics.profit_factor == Decimal("0")
    assert first.metrics.max_drawdown == Decimal("5")
    assert first.metrics.max_drawdown_pct == Decimal("0.0005")
    assert first.metrics.total_return == Decimal("-0.0005")
    assert first.final_position_quantity == 0
    assert first.realized_pnl == Decimal("-3")
    assert first.unrealized_pnl == Decimal("0")
    assert first.total_fees == Decimal("2")
    assert first.net_pnl == Decimal("-5")
    assert first.final_equity == Decimal("9995")
    assert first == second


def test_backtest_slippage_moves_fill_against_trade_direction() -> None:
    assumptions = ExecutionAssumptions(slippage_bps=Decimal("10"))
    pipeline = ReplayStrategyPipeline(
        instrument_id=INSTRUMENT_ID,
        interval=timedelta(minutes=1),
        strategy=EmaCrossoverStrategy(fast_period=1, slow_period=2),
    )
    steps = pipeline.run(
        [
            event("1", 0, "100"),
            event("2", 1, "99"),
            event("3", 2, "101"),
            event("4", 3, "101"),
        ]
    )
    long_decision = next(
        step.decision
        for step in steps
        if step.decision is not None and step.decision.directional
    )

    assert long_decision is not None
    assert assumptions.fill_price(long_decision) == Decimal("101.101")


def test_execution_assumptions_reject_impossible_slippage() -> None:
    with pytest.raises(ValueError, match="slippage_bps"):
        ExecutionAssumptions(slippage_bps=Decimal("10000"))


def test_appending_future_event_does_not_change_already_emitted_trade() -> None:
    prefix = [
        event("1", 0, "100"),
        event("2", 1, "99"),
        event("3", 2, "101"),
        event("4", 3, "101"),
    ]
    first = make_backtester().run(prefix)
    extended = make_backtester().run([*prefix, event("5", 4, "50")])

    assert len(first.trades) == 1
    assert extended.trades[0] == first.trades[0]
    assert first.trades[0].action is DecisionAction.LONG
    assert first.trades[0].reference_price == Decimal("101")


def test_risk_rejections_do_not_create_backtest_trades() -> None:
    result = make_backtester(max_order="50").run(
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
    assert result.metrics.total_return == Decimal("0")
    assert result.metrics.max_drawdown == Decimal("0")
