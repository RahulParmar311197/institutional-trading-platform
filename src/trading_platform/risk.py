import uuid
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from trading_platform.decision import DecisionAction, TradingDecision
from trading_platform.strategy import SignalDirection


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
        decision: TradingDecision,
        *,
        requested_quantity: int,
        current_position_quantity: int = 0,
    ) -> RiskDecision:
        if not decision.directional:
            return RiskDecision(RiskDecisionType.REJECT, "NO_DIRECTIONAL_DECISION", 0)
        if requested_quantity <= 0:
            return RiskDecision(RiskDecisionType.REJECT, "INVALID_QUANTITY", 0)
        if decision.reference_price <= 0:
            return RiskDecision(RiskDecisionType.REJECT, "INVALID_PRICE", 0)

        order_notional = decision.reference_price * Decimal(requested_quantity)
        if order_notional > self.limits.max_order_notional:
            return RiskDecision(RiskDecisionType.REJECT, "MAX_ORDER_NOTIONAL", 0)

        signed_request = (
            requested_quantity
            if decision.action is DecisionAction.LONG
            else -requested_quantity
        )
        projected_quantity = current_position_quantity + signed_request
        projected_notional = abs(Decimal(projected_quantity) * decision.reference_price)
        if projected_notional > self.limits.max_position_notional:
            return RiskDecision(RiskDecisionType.REJECT, "MAX_POSITION_NOTIONAL", 0)

        return RiskDecision(RiskDecisionType.APPROVE, "WITHIN_LIMITS", requested_quantity)


@dataclass(frozen=True, slots=True)
class ApprovedOrderIntent:
    id: uuid.UUID
    decision_id: uuid.UUID
    instrument_id: uuid.UUID
    direction: SignalDirection
    quantity: int
    reference_price: Decimal
    strategy_id: str


def build_approved_intent(
    decision: TradingDecision,
    risk_decision: RiskDecision,
) -> ApprovedOrderIntent:
    if not decision.directional:
        raise ValueError("directional trading decision is required before creating an order intent")
    if (
        risk_decision.decision is not RiskDecisionType.APPROVE
        or risk_decision.approved_quantity <= 0
    ):
        raise ValueError("risk approval is required before creating an order intent")

    direction = (
        SignalDirection.LONG
        if decision.action is DecisionAction.LONG
        else SignalDirection.SHORT
    )
    return ApprovedOrderIntent(
        id=uuid.uuid4(),
        decision_id=decision.id,
        instrument_id=decision.instrument_id,
        direction=direction,
        quantity=risk_decision.approved_quantity,
        reference_price=decision.reference_price,
        strategy_id=decision.strategy_id,
    )
