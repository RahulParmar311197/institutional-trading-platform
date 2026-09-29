from collections.abc import Sequence
from decimal import Decimal


def sma(values: Sequence[Decimal], period: int) -> Decimal:
    if period <= 0:
        raise ValueError("period must be positive")
    if len(values) < period:
        raise ValueError("insufficient values for SMA")
    window = values[-period:]
    return sum(window, Decimal("0")) / Decimal(period)


def ema(values: Sequence[Decimal], period: int) -> Decimal:
    if period <= 0:
        raise ValueError("period must be positive")
    if len(values) < period:
        raise ValueError("insufficient values for EMA")
    alpha = Decimal("2") / Decimal(period + 1)
    seed = sum(values[:period], Decimal("0")) / Decimal(period)
    current = seed
    for value in values[period:]:
        current = (value * alpha) + (current * (Decimal("1") - alpha))
    return current


def rsi(values: Sequence[Decimal], period: int = 14) -> Decimal:
    if period <= 0:
        raise ValueError("period must be positive")
    if len(values) < period + 1:
        raise ValueError("insufficient values for RSI")

    gains = Decimal("0")
    losses = Decimal("0")
    deltas = [values[index] - values[index - 1] for index in range(1, period + 1)]
    for delta in deltas:
        if delta > 0:
            gains += delta
        elif delta < 0:
            losses += -delta

    average_gain = gains / Decimal(period)
    average_loss = losses / Decimal(period)

    for index in range(period + 1, len(values)):
        delta = values[index] - values[index - 1]
        gain = delta if delta > 0 else Decimal("0")
        loss = -delta if delta < 0 else Decimal("0")
        average_gain = ((average_gain * Decimal(period - 1)) + gain) / Decimal(period)
        average_loss = ((average_loss * Decimal(period - 1)) + loss) / Decimal(period)

    if average_loss == 0:
        return Decimal("100")
    if average_gain == 0:
        return Decimal("0")

    relative_strength = average_gain / average_loss
    return Decimal("100") - (Decimal("100") / (Decimal("1") + relative_strength))
