import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trading_platform.pipeline import ReplayStrategyPipeline
from trading_platform.recorded_events import RecordedEventType, RecordedMarketEvent
from trading_platform.strategy import EmaCrossoverStrategy, SignalDirection

INSTRUMENT_ID = uuid.uuid4()
BASE = datetime(2026, 1, 1, 9, 15, tzinfo=UTC)


def event(event_id: str, minute: int, price: str) -> RecordedMarketEvent:
    timestamp = BASE + timedelta(minutes=minute)
    return RecordedMarketEvent(
        event_id=event_id,
        event_type=RecordedEventType.TRADE,
        instrument_id=INSTRUMENT_ID,
        source="fixture",
        exchange_timestamp=timestamp,
        provider_timestamp=timestamp,
        ingestion_timestamp=timestamp,
        sequence=minute,
        price=Decimal(price),
        quantity=1,
    )


def test_replay_pipeline_emits_strategy_only_after_required_closed_history() -> None:
    pipeline = ReplayStrategyPipeline(
        instrument_id=INSTRUMENT_ID,
        interval=timedelta(minutes=1),
        strategy=EmaCrossoverStrategy(fast_period=1, slow_period=2),
    )

    results = pipeline.run(
        [
            event("4", 3, "101"),
            event("1", 0, "100"),
            event("3", 2, "101"),
            event("2", 1, "99"),
        ]
    )

    assert len(pipeline.closed_candles) == 3
    assert [c.close for c in pipeline.closed_candles] == [
        Decimal("100"),
        Decimal("99"),
        Decimal("101"),
    ]
    assert results[-1].signal is not None
    assert results[-1].signal.direction is SignalDirection.LONG
    assert results[-1].decision is not None
    assert results[-1].decision.directional is True


def test_replay_pipeline_is_repeatable_after_reset() -> None:
    events = [event("1", 0, "100"), event("2", 1, "99"), event("3", 2, "101"), event("4", 3, "101")]
    pipeline = ReplayStrategyPipeline(
        instrument_id=INSTRUMENT_ID,
        interval=timedelta(minutes=1),
        strategy=EmaCrossoverStrategy(fast_period=1, slow_period=2),
    )

    first = pipeline.run(events)
    first_summary = [
        (
            step.closed_candle.close if step.closed_candle else None,
            step.signal.direction if step.signal else None,
            step.signal.reason if step.signal else None,
            step.decision.action if step.decision else None,
        )
        for step in first
    ]

    pipeline.reset()
    second = pipeline.run(events)
    second_summary = [
        (
            step.closed_candle.close if step.closed_candle else None,
            step.signal.direction if step.signal else None,
            step.signal.reason if step.signal else None,
            step.decision.action if step.decision else None,
        )
        for step in second
    ]

    assert first_summary == second_summary


def test_replay_pipeline_rejects_wrong_instrument() -> None:
    pipeline = ReplayStrategyPipeline(
        instrument_id=INSTRUMENT_ID,
        interval=timedelta(minutes=1),
        strategy=EmaCrossoverStrategy(fast_period=1, slow_period=2),
    )
    wrong = event("wrong", 0, "100")
    object.__setattr__(wrong, "instrument_id", uuid.uuid4())

    with pytest.raises(ValueError, match="does not match"):
        pipeline.process_event(wrong)
