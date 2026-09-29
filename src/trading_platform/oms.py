import uuid
from dataclasses import dataclass, field
from enum import StrEnum

from trading_platform.risk import ApprovedOrderIntent


class OrderState(StrEnum):
    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass(slots=True)
class ManagedOrder:
    id: uuid.UUID
    intent: ApprovedOrderIntent
    state: OrderState = OrderState.CREATED
    filled_quantity: int = 0
    processed_fill_ids: set[str] = field(default_factory=set)

    def submit(self) -> None:
        if self.state is not OrderState.CREATED:
            raise ValueError("only CREATED orders can be submitted")
        self.state = OrderState.SUBMITTED

    def apply_fill(self, *, fill_id: str, quantity: int) -> None:
        if fill_id in self.processed_fill_ids:
            return
        if self.state not in {OrderState.SUBMITTED, OrderState.PARTIALLY_FILLED}:
            raise ValueError("order is not fillable in its current state")
        if quantity <= 0:
            raise ValueError("fill quantity must be positive")
        if self.filled_quantity + quantity > self.intent.quantity:
            raise ValueError("fill would exceed ordered quantity")

        self.processed_fill_ids.add(fill_id)
        self.filled_quantity += quantity
        if self.filled_quantity == self.intent.quantity:
            self.state = OrderState.FILLED
        else:
            self.state = OrderState.PARTIALLY_FILLED

    def cancel(self) -> None:
        cancellable_states = {
            OrderState.CREATED,
            OrderState.SUBMITTED,
            OrderState.PARTIALLY_FILLED,
        }
        if self.state not in cancellable_states:
            raise ValueError("order cannot be cancelled in its current state")
        self.state = OrderState.CANCELLED


class OrderManagementSystem:
    def __init__(self) -> None:
        self._orders: dict[uuid.UUID, ManagedOrder] = {}

    def create(self, intent: ApprovedOrderIntent) -> ManagedOrder:
        order = ManagedOrder(id=uuid.uuid4(), intent=intent)
        self.register(order)
        return order

    def register(self, order: ManagedOrder) -> None:
        if order.id in self._orders:
            raise ValueError(f"order {order.id} is already registered")
        self._orders[order.id] = order

    def get(self, order_id: uuid.UUID) -> ManagedOrder:
        try:
            return self._orders[order_id]
        except KeyError as exc:
            raise KeyError(f"unknown order {order_id}") from exc
