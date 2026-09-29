import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trading_platform.candles import Candle
from trading_platform.smc import (
    GapDirection,
    GapState,
    detect_fair_value_gaps,
    evaluate_gap_lifecycle,
)

INSTRUMENT_ID = uuid.uuid4()
BASE = datetime(2026, 1, 1, 9, 15, tzinfo=UTC)


def candle(
    index: int,
    *,
    high: str,
    low: str,
    close: str,
    closed: bool = True,
) -> Candle:
    start = BASE + timedelta(minutes=index)
    return Candle(
        instrument_id=INSTRUMENT_ID,
        start=start,
        end=start + timedelta(minutes=1),
        open=Decimal(close),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=1,
        closed=closed,
    )


def bullish_gap() -> tuple[list[Candle], object]:
    candles = [
        candle(0, high="100", low="95", close="98"),
        candle(1, high="108", low="99", close="106"),
        candle(2, high="112", low="103", close="110"),
    ]
    return candles, detect_fair_value_gaps(candles)[0]


def test_bullish_fvg_is_confirmed_by_third_closed_candle() -> None:
    candles = [
        candle(0, high="100", low="95", close="98"),
        candle(1, high="108", low="99", close="106"),
        candle(2, high="112", low="103", close="110"),
    ]

    gaps = detect_fair_value_gaps(candles)

    assert len(gaps) == 1
    gap = gaps[0]
    assert gap.direction is GapDirection.BULLISH
    assert gap.lower_bound == Decimal("100")
    assert gap.upper_bound == Decimal("103")
    assert gap.midpoint == Decimal("101.5")
    assert gap.confirmed_at == candles[2].end


def test_bearish_fvg_has_ordered_price_bounds() -> None:
    candles = [
        candle(0, high="110", low="105", close="107"),
        candle(1, high="106", low="98", close="100"),
        candle(2, high="102", low="95", close="97"),
    ]

    gaps = detect_fair_value_gaps(candles)

    assert len(gaps) == 1
    gap = gaps[0]
    assert gap.direction is GapDirection.BEARISH
    assert gap.lower_bound == Decimal("102")
    assert gap.upper_bound == Decimal("105")


def test_no_gap_when_wicks_overlap() -> None:
    candles = [
        candle(0, high="100", low="95", close="98"),
        candle(1, high="104", low="97", close="102"),
        candle(2, high="105", low="99", close="103"),
    ]

    assert detect_fair_value_gaps(candles) == []


def test_fvg_rejects_open_candles() -> None:
    candles = [
        candle(0, high="100", low="95", close="98"),
        candle(1, high="108", low="99", close="106"),
        candle(2, high="112", low="103", close="110", closed=False),
    ]

    with pytest.raises(ValueError, match="closed candles only"):
        detect_fair_value_gaps(candles)


def test_bullish_fvg_lifecycle_open_partial_filled_and_invalidated() -> None:
    seed, raw_gap = bullish_gap()
    from trading_platform.smc import FairValueGap

    assert isinstance(raw_gap, FairValueGap)
    gap = raw_gap

    assert evaluate_gap_lifecycle(gap, seed).state is GapState.OPEN

    partial = seed + [candle(3, high="110", low="102", close="105")]
    partial_state = evaluate_gap_lifecycle(gap, partial)
    assert partial_state.state is GapState.PARTIALLY_MITIGATED
    assert partial_state.first_touched_at == partial[-1].end

    filled = partial + [candle(4, high="106", low="100", close="102")]
    filled_state = evaluate_gap_lifecycle(gap, filled)
    assert filled_state.state is GapState.FILLED
    assert filled_state.filled_at == filled[-1].end

    invalidated = filled + [candle(5, high="102", low="98", close="99")]
    invalidated_state = evaluate_gap_lifecycle(gap, invalidated)
    assert invalidated_state.state is GapState.INVALIDATED
    assert invalidated_state.invalidated_at == invalidated[-1].end


def test_fvg_lifecycle_ignores_candles_at_or_before_confirmation() -> None:
    seed, raw_gap = bullish_gap()
    from trading_platform.smc import FairValueGap

    assert isinstance(raw_gap, FairValueGap)
    gap = raw_gap
    earlier_touch = candle(1, high="103", low="99", close="101")

    lifecycle = evaluate_gap_lifecycle(gap, [seed[0], earlier_touch, seed[2]])

    assert lifecycle.state is GapState.OPEN
