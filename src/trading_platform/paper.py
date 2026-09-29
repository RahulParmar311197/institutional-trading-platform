import uuid
from dataclasses import dataclass
from decimal import Decimal

from trading_platform.oms import ManagedOrder
from trading_platform.strategy import SignalDirection


@dataclass(slots=True)
class Position:
    quantity: int = 0
    average_price: Decimal = Decimal("0")

    def apply_fill(self, *, direction: SignalDirection, quantity: int, price: Decimal) -> None:
        if quantity <= 0 or price <= 0:
            raise ValueError("fill quantity and price must be positive")
        signed_quantity = quantity if direction is SignalDirection.LONG else -quantity
        new_quantity = self.quantity + signed_quantity

        same_direction = self.quantity == 0 or (self.quantity > 0) == (signed_quantity > 0)
        if same_direction:
            total_cost = (self.average_price * Decimal(abs(self.quantity))) + (
                price * Decimal(quantity)
            )
            self.quantity = new_quantity
            self.average_price = total_cost / Decimal(abs(self.quantity))
            return

        if new_quantity == 0:
            self.quantity = 0
            self.average_price = Decimal("0")
            return

        if (self.quantity > 0) != (new_quantity > 0):
            self.quantity = new_quantity
            self.average_price = price
            return

        self.quantity = new_quantity


class PaperBroker:
    def __init__(self) -> None:
        self.positions: dict[uuid.UUID, Position] = {}

    def execute_market(self, order: ManagedOrder, *, fill_id: str, price: Decimal) -> None:
        if price <= 0:
            raise ValueError("fill price must be positive")
        remaining = order.intent.quantity - order.filled_quantity
        if remaining <= 0:
            return

        before = order.filled_quantity
        order.apply_fill(fill_id=fill_id, quantity=remaining)
        executed = order.filled_quantity - before
        if executed == 0:
            return

        position = self.positions.setdefault(order.intent.instrument_id, Position())
        position.apply_fill(
            direction=order.intent.direction,
            quantity=executed,
            price=price,
        )
