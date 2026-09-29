import uuid
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from trading_platform.strategy import SignalDirection, StrategySignal


class RiskDecisionType(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


@dataclass(frozen=True, slots=True)
class RiskLimits:
    max_order_notional: Decimal
    max_position_notional: Decimal


@dataclass(frozen=True, slots=True)
class RiskDecision:
    decision: RiskDecisionType
    reason: str
    approved_quantity: int


class RiskEngine:
    def __init__(self, limits: RiskLimits) -> None:
        if limits.max_order_notional <= 0 or limits.max_position_notional <= 0:
            raise ValueError("risk limits must be positive")
        self.limits = limits

    def evaluate(
        self,
        signal: StrategySignal,
        *,
        requested_quantity: int,
        current_position_quantity: int = 0,
    ) -> RiskDecision:
        if signal.direction is SignalDirection.FLAT:
            return RiskDecision(RiskDecisionType.REJECT, "NO_DIRECTIONAL_SIGNAL", 0)
        if requested_quantity <= 0:
            return RiskDecision(RiskDecisionType.REJECT, "INVALID_QUANTITY", 0)
        if signal.price <= 0:
            return RiskDecision(RiskDecisionType.REJECT, "INVALID_PRICE", 0)

        order_notional = signal.price * Decimal(requested_quantity)
        if order_notional > self.limits.max_order_notional:
            return RiskDecision(RiskDecisionType.REJECT, "MAX_ORDER_NOTIONAL", 0)

        signed_request = (
            requested_quantity
            if signal.direction is SignalDirection.LONG
            else -requested_quantity
        )
        projected_quantity = current_position_quantity + signed_request
        projected_notional = abs(Decimal(projected_quantity) * signal.price)
        if projected_notional > self.limits.max_position_notional:
            return RiskDecision(RiskDecisionType.REJECT, "MAX_POSITION_NOTIONAL", 0)

        return RiskDecision(RiskDecisionType.APPROVE, "WITHIN_LIMITS", requested_quantity)


@dataclass(frozen=True, slots=True)
class ApprovedOrderIntent:
    id: uuid.UUID
    instrument_id: uuid.UUID
    direction: SignalDirection
    quantity: int
    reference_price: Decimal
    strategy_id: str


def build_approved_intent(
    signal: StrategySignal,
    decision: RiskDecision,
) -> ApprovedOrderIntent:
    if decision.decision is not RiskDecisionType.APPROVE or decision.approved_quantity <= 0:
        raise ValueError("risk approval is required before creating an order intent")
    return ApprovedOrderIntent(
        id=uuid.uuid4(),
        instrument_id=signal.instrument_id,
        direction=signal.direction,
        quantity=decision.approved_quantity,
        reference_price=signal.price,
        strategy_id=signal.strategy_id,
    )
