import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from trading_platform.candles import Candle
from trading_platform.indicators import ema

EMA_CROSSOVER_STRATEGY_VERSION = 1


class SignalDirection(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


class StrategyLifecycle(StrEnum):
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"


@dataclass(frozen=True, slots=True)
class StrategySignal:
    instrument_id: uuid.UUID
    direction: SignalDirection
    price: Decimal
    strategy_id: str
    reason: str


class StrategyEvaluator(Protocol):
    strategy_id: str

    @property
    def minimum_history(self) -> int: ...

    def evaluate(self, candles: list[Candle]) -> StrategySignal: ...


@dataclass(frozen=True, slots=True)
class StrategyDescriptor:
    strategy_id: str
    family: str
    version: int
    minimum_history: int
    lifecycle: StrategyLifecycle


@dataclass(frozen=True, slots=True)
class _StrategyRegistration:
    descriptor: StrategyDescriptor
    factory: Callable[[], StrategyEvaluator]


class StrategyRegistry:
    def __init__(self) -> None:
        self._registrations: dict[str, _StrategyRegistration] = {}

    @property
    def descriptors(self) -> tuple[StrategyDescriptor, ...]:
        return tuple(
            registration.descriptor
            for _, registration in sorted(self._registrations.items())
        )

    def register(
        self,
        factory: Callable[[], StrategyEvaluator],
        *,
        family: str,
        version: int,
    ) -> StrategyDescriptor:
        normalized_family = family.strip()
        if not normalized_family:
            raise ValueError("strategy family must be non-empty")
        if version <= 0:
            raise ValueError("strategy version must be positive")

        strategy = factory()
        strategy_id = _validated_strategy_id(strategy)
        minimum_history = _validated_minimum_history(strategy)
        if strategy_id in self._registrations:
            raise ValueError(f"strategy {strategy_id!r} is already registered")

        descriptor = StrategyDescriptor(
            strategy_id=strategy_id,
            family=normalized_family,
            version=version,
            minimum_history=minimum_history,
            lifecycle=StrategyLifecycle.ACTIVE,
        )
        self._registrations[strategy_id] = _StrategyRegistration(descriptor, factory)
        return descriptor

    def retire(self, strategy_id: str) -> StrategyDescriptor:
        registration = self._get_registration(strategy_id)
        if registration.descriptor.lifecycle is StrategyLifecycle.RETIRED:
            return registration.descriptor
        descriptor = replace(
            registration.descriptor,
            lifecycle=StrategyLifecycle.RETIRED,
        )
        self._registrations[strategy_id] = _StrategyRegistration(
            descriptor,
            registration.factory,
        )
        return descriptor

    def create(
        self,
        strategy_id: str,
        *,
        allow_retired: bool = False,
    ) -> StrategyEvaluator:
        registration = self._get_registration(strategy_id)
        descriptor = registration.descriptor
        if descriptor.lifecycle is StrategyLifecycle.RETIRED and not allow_retired:
            raise ValueError(f"strategy {strategy_id!r} is retired")

        strategy = registration.factory()
        if _validated_strategy_id(strategy) != descriptor.strategy_id:
            raise RuntimeError("strategy factory produced a different strategy identity")
        if _validated_minimum_history(strategy) != descriptor.minimum_history:
            raise RuntimeError("strategy factory changed minimum-history semantics")
        return strategy

    def descriptor(self, strategy_id: str) -> StrategyDescriptor:
        return self._get_registration(strategy_id).descriptor

    def _get_registration(self, strategy_id: str) -> _StrategyRegistration:
        try:
            return self._registrations[strategy_id]
        except KeyError as exc:
            raise KeyError(f"strategy {strategy_id!r} is not registered") from exc


def _validated_strategy_id(strategy: StrategyEvaluator) -> str:
    strategy_id = strategy.strategy_id
    if not isinstance(strategy_id, str) or not strategy_id.strip():
        raise ValueError("strategy_id must be a non-empty string")
    return strategy_id


def _validated_minimum_history(strategy: StrategyEvaluator) -> int:
    minimum_history = strategy.minimum_history
    if type(minimum_history) is not int or minimum_history <= 0:
        raise ValueError("strategy minimum_history must be a positive integer")
    return minimum_history


class EmaCrossoverStrategy:
    def __init__(self, *, fast_period: int = 5, slow_period: int = 20) -> None:
        if fast_period <= 0 or slow_period <= 0 or fast_period >= slow_period:
            raise ValueError("require 0 < fast_period < slow_period")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.strategy_id = (
            f"ema_crossover_v{EMA_CROSSOVER_STRATEGY_VERSION}_"
            f"{fast_period}_{slow_period}"
        )

    @property
    def minimum_history(self) -> int:
        return self.slow_period + 1

    def evaluate(self, candles: list[Candle]) -> StrategySignal:
        if not candles:
            raise ValueError("at least one candle is required")
        if any(not candle.closed for candle in candles):
            raise ValueError("strategy may evaluate closed candles only")
        if len(candles) < self.minimum_history:
            raise ValueError("insufficient candles for strategy")

        closes = [candle.close for candle in candles]
        previous = closes[:-1]
        fast_previous = ema(previous, self.fast_period)
        slow_previous = ema(previous, self.slow_period)
        fast_current = ema(closes, self.fast_period)
        slow_current = ema(closes, self.slow_period)
        last = candles[-1]

        if fast_previous <= slow_previous and fast_current > slow_current:
            direction = SignalDirection.LONG
            reason = "FAST_EMA_CROSSED_ABOVE_SLOW_EMA"
        elif fast_previous >= slow_previous and fast_current < slow_current:
            direction = SignalDirection.SHORT
            reason = "FAST_EMA_CROSSED_BELOW_SLOW_EMA"
        else:
            direction = SignalDirection.FLAT
            reason = "NO_CROSSOVER"

        return StrategySignal(
            instrument_id=last.instrument_id,
            direction=direction,
            price=last.close,
            strategy_id=self.strategy_id,
            reason=reason,
        )
