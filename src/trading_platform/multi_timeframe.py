import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from trading_platform.candles import Candle, Trade
from trading_platform.sessions import TradingSession


@dataclass(slots=True)
class SessionCandleBuilder:
    instrument_id: uuid.UUID
    interval: timedelta
    session: TradingSession
    _trades: list[Trade] = field(default_factory=list, init=False)
    _start: datetime | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.interval <= timedelta(0):
            raise ValueError("interval must be positive")

    def add(self, trade: Trade) -> Candle | None:
        if trade.instrument_id != self.instrument_id:
            raise ValueError("trade instrument does not match candle builder")
        if trade.price <= 0 or trade.quantity <= 0:
            raise ValueError("trade price and quantity must be positive")
        if not self.session.contains(trade.timestamp):
            raise ValueError("trade timestamp is outside the configured session")
        if self._trades and trade.timestamp < self._trades[-1].timestamp:
            raise ValueError("out-of-order trade")

        bucket_start = self.session.bucket_start(trade.timestamp, self.interval)
        if self._start is None:
            self._start = bucket_start
        elif bucket_start != self._start:
            completed = self.snapshot(closed=True)
            self._trades = [trade]
            self._start = bucket_start
            return completed

        self._trades.append(trade)
        return None

    def snapshot(self, *, closed: bool = False) -> Candle:
        if not self._trades or self._start is None:
            raise ValueError("cannot snapshot an empty candle")
        prices = [trade.price for trade in self._trades]
        _, session_close = self.session.bounds_for(self._trades[-1].timestamp)
        end = min(self._start + self.interval, session_close.astimezone(self._start.tzinfo))
        return Candle(
            instrument_id=self.instrument_id,
            start=self._start,
            end=end,
            open=prices[0],
            high=max(prices),
            low=min(prices),
            close=prices[-1],
            volume=sum(trade.quantity for trade in self._trades),
            closed=closed,
        )


class MultiTimeframeCandleEngine:
    def __init__(
        self,
        instrument_id: uuid.UUID,
        *,
        session: TradingSession,
        intervals: tuple[timedelta, ...],
    ) -> None:
        if not intervals:
            raise ValueError("at least one interval is required")
        if len(set(intervals)) != len(intervals):
            raise ValueError("intervals must be unique")
        self.builders = {
            interval: SessionCandleBuilder(instrument_id, interval, session)
            for interval in intervals
        }

    def add(self, trade: Trade) -> dict[timedelta, Candle]:
        completed: dict[timedelta, Candle] = {}
        for interval, builder in self.builders.items():
            candle = builder.add(trade)
            if candle is not None:
                completed[interval] = candle
        return completed
