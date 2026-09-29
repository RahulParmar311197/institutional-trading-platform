import uuid
from decimal import Decimal

from trading_platform.paper import Position
from trading_platform.reconciliation import reconcile_positions
from trading_platform.strategy import SignalDirection


def test_long_position_realizes_profit_on_partial_close() -> None:
    position = Position()
    position.apply_fill(
        direction=SignalDirection.LONG,
        quantity=10,
        price=Decimal("100"),
    )
    position.apply_fill(
        direction=SignalDirection.SHORT,
        quantity=4,
        price=Decimal("110"),
    )

    assert position.quantity == 6
    assert position.average_price == Decimal("100")
    assert position.realized_pnl == Decimal("40")
    assert position.unrealized_pnl(Decimal("105")) == Decimal("30")


def test_short_position_realizes_profit_on_cover() -> None:
    position = Position()
    position.apply_fill(
        direction=SignalDirection.SHORT,
        quantity=10,
        price=Decimal("100"),
    )
    position.apply_fill(
        direction=SignalDirection.LONG,
        quantity=10,
        price=Decimal("90"),
    )

    assert position.quantity == 0
    assert position.average_price == Decimal("0")
    assert position.realized_pnl == Decimal("100")


def test_position_reversal_uses_new_fill_price_for_remaining_position() -> None:
    position = Position()
    position.apply_fill(
        direction=SignalDirection.LONG,
        quantity=5,
        price=Decimal("100"),
    )
    position.apply_fill(
        direction=SignalDirection.SHORT,
        quantity=8,
        price=Decimal("95"),
    )

    assert position.quantity == -3
    assert position.average_price == Decimal("95")
    assert position.realized_pnl == Decimal("-25")


def test_reconciliation_reports_quantity_or_price_mismatch() -> None:
    instrument_id = uuid.uuid4()
    expected = {
        instrument_id: Position(quantity=5, average_price=Decimal("100")),
    }
    actual = {
        instrument_id: Position(quantity=4, average_price=Decimal("101")),
    }

    result = reconcile_positions(expected, actual)

    assert result.matched is False
    assert len(result.mismatches) == 1
    mismatch = result.mismatches[0]
    assert mismatch.instrument_id == instrument_id
    assert mismatch.expected_quantity == 5
    assert mismatch.actual_quantity == 4


def test_reconciliation_succeeds_for_equal_snapshots() -> None:
    instrument_id = uuid.uuid4()
    expected = {
        instrument_id: Position(quantity=5, average_price=Decimal("100")),
    }
    actual = {
        instrument_id: Position(quantity=5, average_price=Decimal("100")),
    }

    result = reconcile_positions(expected, actual)

    assert result.matched is True
    assert result.mismatches == ()
