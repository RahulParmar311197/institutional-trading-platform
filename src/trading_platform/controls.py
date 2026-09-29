import uuid
from dataclasses import dataclass
from enum import StrEnum

from trading_platform.decision import TradingDecision


class OperationalMode(StrEnum):
    NORMAL = "NORMAL"
    READ_ONLY = "READ_ONLY"
    CLOSE_ONLY = "CLOSE_ONLY"
    HALTED = "HALTED"


class KillSwitchScope(StrEnum):
    GLOBAL = "GLOBAL"
    ACCOUNT = "ACCOUNT"
    STRATEGY = "STRATEGY"
    INSTRUMENT = "INSTRUMENT"


@dataclass(frozen=True, slots=True)
class RiskLock:
    scope: KillSwitchScope
    key: str | None
    reason: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("risk lock reason must not be empty")
        if self.scope is KillSwitchScope.GLOBAL and self.key is not None:
            raise ValueError("global risk lock must not define a key")
        if self.scope is not KillSwitchScope.GLOBAL and not self.key:
            raise ValueError("non-global risk lock requires a key")


class RiskControlBook:
    def __init__(self) -> None:
        self.mode = OperationalMode.NORMAL
        self._locks: dict[tuple[KillSwitchScope, str | None], RiskLock] = {}

    @property
    def locks(self) -> tuple[RiskLock, ...]:
        return tuple(self._locks.values())

    def set_mode(self, mode: OperationalMode) -> None:
        self.mode = mode

    def activate(
        self,
        scope: KillSwitchScope,
        *,
        reason: str,
        key: str | None = None,
    ) -> RiskLock:
        lock = RiskLock(scope=scope, key=key, reason=reason)
        self._locks[(scope, key)] = lock
        return lock

    def clear(self, scope: KillSwitchScope, *, key: str | None = None) -> bool:
        return self._locks.pop((scope, key), None) is not None

    def blocking_reason(
        self,
        decision: TradingDecision,
        *,
        account_id: str | None = None,
    ) -> str | None:
        global_lock = self._locks.get((KillSwitchScope.GLOBAL, None))
        if global_lock is not None:
            return f"GLOBAL_KILL_SWITCH:{global_lock.reason}"

        if account_id is not None:
            account_lock = self._locks.get((KillSwitchScope.ACCOUNT, account_id))
            if account_lock is not None:
                return f"ACCOUNT_KILL_SWITCH:{account_lock.reason}"

        strategy_lock = self._locks.get((KillSwitchScope.STRATEGY, decision.strategy_id))
        if strategy_lock is not None:
            return f"STRATEGY_KILL_SWITCH:{strategy_lock.reason}"

        instrument_key = str(decision.instrument_id)
        instrument_lock = self._locks.get((KillSwitchScope.INSTRUMENT, instrument_key))
        if instrument_lock is not None:
            return f"INSTRUMENT_KILL_SWITCH:{instrument_lock.reason}"

        if self.mode is OperationalMode.HALTED:
            return "OPERATIONAL_MODE_HALTED"
        if self.mode is OperationalMode.READ_ONLY:
            return "OPERATIONAL_MODE_READ_ONLY"
        return None

    def allows_close_only_transition(
        self,
        *,
        current_position_quantity: int,
        projected_position_quantity: int,
    ) -> bool:
        if self.mode is not OperationalMode.CLOSE_ONLY:
            return True
        if current_position_quantity == 0:
            return False
        if projected_position_quantity == 0:
            return True
        same_side = (current_position_quantity > 0) == (projected_position_quantity > 0)
        return same_side and abs(projected_position_quantity) < abs(current_position_quantity)


def instrument_lock_key(instrument_id: uuid.UUID) -> str:
    return str(instrument_id)
