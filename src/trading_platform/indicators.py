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


def atr(
    highs: Sequence[Decimal],
    lows: Sequence[Decimal],
    closes: Sequence[Decimal],
    period: int = 14,
) -> Decimal:
    if period <= 0:
        raise ValueError("period must be positive")
    if not (len(highs) == len(lows) == len(closes)):
        raise ValueError("high, low and close series must have equal length")
    if len(closes) < period + 1:
        raise ValueError("insufficient values for ATR")

    true_ranges: list[Decimal] = []
    for index in range(1, len(closes)):
        high = highs[index]
        low = lows[index]
        previous_close = closes[index - 1]
        if high < low:
            raise ValueError("high must be greater than or equal to low")
        true_ranges.append(
            max(
                high - low,
                abs(high - previous_close),
                abs(low - previous_close),
            )
        )

    current = sum(true_ranges[:period], Decimal("0")) / Decimal(period)
    for true_range in true_ranges[period:]:
        current = (
            (current * Decimal(period - 1)) + true_range
        ) / Decimal(period)
    return current


def vwap(prices: Sequence[Decimal], volumes: Sequence[int]) -> Decimal:
    if len(prices) != len(volumes):
        raise ValueError("price and volume series must have equal length")
    if not prices:
        raise ValueError("VWAP requires at least one observation")
    if any(price <= 0 for price in prices):
        raise ValueError("prices must be positive")
    if any(volume < 0 for volume in volumes):
        raise ValueError("volumes must be non-negative")

    total_volume = sum(volumes)
    if total_volume <= 0:
        raise ValueError("VWAP requires positive total volume")
    weighted_sum = sum(
        (price * Decimal(volume) for price, volume in zip(prices, volumes, strict=True)),
        Decimal("0"),
    )
    return weighted_sum / Decimal(total_volume)
