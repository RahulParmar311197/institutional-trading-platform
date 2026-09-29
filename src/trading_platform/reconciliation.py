import uuid
from dataclasses import dataclass
from decimal import Decimal

from trading_platform.paper import Position


@dataclass(frozen=True, slots=True)
class PositionMismatch:
    instrument_id: uuid.UUID
    expected_quantity: int
    actual_quantity: int
    expected_average_price: Decimal
    actual_average_price: Decimal


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    matched: bool
    mismatches: tuple[PositionMismatch, ...]


def reconcile_positions(
    expected: dict[uuid.UUID, Position],
    actual: dict[uuid.UUID, Position],
) -> ReconciliationResult:
    mismatches: list[PositionMismatch] = []
    instrument_ids = set(expected) | set(actual)

    for instrument_id in sorted(instrument_ids, key=str):
        expected_position = expected.get(instrument_id, Position())
        actual_position = actual.get(instrument_id, Position())
        if (
            expected_position.quantity != actual_position.quantity
            or expected_position.average_price != actual_position.average_price
        ):
            mismatches.append(
                PositionMismatch(
                    instrument_id=instrument_id,
                    expected_quantity=expected_position.quantity,
                    actual_quantity=actual_position.quantity,
                    expected_average_price=expected_position.average_price,
                    actual_average_price=actual_position.average_price,
                )
            )

    return ReconciliationResult(matched=not mismatches, mismatches=tuple(mismatches))
