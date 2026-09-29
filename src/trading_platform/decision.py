import uuid
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from trading_platform.strategy import SignalDirection, StrategySignal


class DecisionAction(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"
    HOLD = "HOLD"
    NO_TRADE = "NO_TRADE"


@dataclass(frozen=True, slots=True)
class TradingDecision:
    id: uuid.UUID
    instrument_id: uuid.UUID
    action: DecisionAction
    reference_price: Decimal
    strategy_id: str
    reason: str

    @property
    def directional(self) -> bool:
        return self.action in {DecisionAction.LONG, DecisionAction.SHORT}


def decide(signal: StrategySignal) -> TradingDecision:
    if signal.price <= 0:
        return TradingDecision(
            id=uuid.uuid4(),
            instrument_id=signal.instrument_id,
            action=DecisionAction.NO_TRADE,
            reference_price=signal.price,
            strategy_id=signal.strategy_id,
            reason="INVALID_REFERENCE_PRICE",
        )

    if signal.direction is SignalDirection.LONG:
        action = DecisionAction.LONG
    elif signal.direction is SignalDirection.SHORT:
        action = DecisionAction.SHORT
    else:
        action = DecisionAction.HOLD

    return TradingDecision(
        id=uuid.uuid4(),
        instrument_id=signal.instrument_id,
        action=action,
        reference_price=signal.price,
        strategy_id=signal.strategy_id,
        reason=signal.reason,
    )


def to_signal(decision: TradingDecision) -> StrategySignal:
    if decision.action is DecisionAction.LONG:
        direction = SignalDirection.LONG
    elif decision.action is DecisionAction.SHORT:
        direction = SignalDirection.SHORT
    else:
        direction = SignalDirection.FLAT

    return StrategySignal(
        instrument_id=decision.instrument_id,
        direction=direction,
        price=decision.reference_price,
        strategy_id=decision.strategy_id,
        reason=decision.reason,
    )
