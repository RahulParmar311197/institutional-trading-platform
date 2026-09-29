import uuid
from datetime import timedelta

from trading_platform.candles import Candle
from trading_platform.provider_historical import HistoricalBar


def bars_to_closed_candles(
    *,
    instrument_id: uuid.UUID,
    bars: tuple[HistoricalBar, ...],
    interval: timedelta,
) -> tuple[Candle, ...]:
    if interval <= timedelta(0):
        raise ValueError("interval must be positive")

    ordered = sorted(bars, key=lambda item: item.timestamp)
    timestamps = [bar.timestamp for bar in ordered]
    if len(set(timestamps)) != len(timestamps):
        raise ValueError("historical bars contain duplicate timestamps")

    return tuple(
        Candle(
            instrument_id=instrument_id,
            start=bar.timestamp,
            end=bar.timestamp + interval,
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
            closed=True,
        )
        for bar in ordered
    )
