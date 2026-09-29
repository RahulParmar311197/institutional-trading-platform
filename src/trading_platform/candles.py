import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Trade:
    instrument_id: uuid.UUID
    timestamp: datetime
    price: Decimal
    quantity: int


@dataclass(frozen=True, slots=True)
class Candle:
    instrument_id: uuid.UUID
    start: datetime
    end: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    closed: bool


class CandleBuilder:
    def __init__(self, instrument_id: uuid.UUID, *, interval: timedelta) -> None:
        if interval <= timedelta(0):
            raise ValueError("interval must be positive")
        self.instrument_id = instrument_id
        self.interval = interval
        self._trades: list[Trade] = []
        self._start: datetime | None = None

    def add(self, trade: Trade) -> Candle | None:
        if trade.instrument_id != self.instrument_id:
            raise ValueError("trade instrument does not match candle builder")
        if trade.price <= 0 or trade.quantity <= 0:
            raise ValueError("trade price and quantity must be positive")
        if self._trades and trade.timestamp < self._trades[-1].timestamp:
            raise ValueError("out-of-order trade")

        start = self._start
        if start is None:
            start = self._bucket_start(trade.timestamp)
            self._start = start

        if trade.timestamp >= start + self.interval:
            completed = self.snapshot(closed=True)
            self._trades = []
            self._start = self._bucket_start(trade.timestamp)
            self._trades.append(trade)
            return completed

        self._trades.append(trade)
        return None

    def snapshot(self, *, closed: bool = False) -> Candle:
        if not self._trades or self._start is None:
            raise ValueError("cannot snapshot an empty candle")
        prices = [trade.price for trade in self._trades]
        return Candle(
            instrument_id=self.instrument_id,
            start=self._start,
            end=self._start + self.interval,
            open=prices[0],
            high=max(prices),
            low=min(prices),
            close=prices[-1],
            volume=sum(trade.quantity for trade in self._trades),
            closed=closed,
        )

    def _bucket_start(self, timestamp: datetime) -> datetime:
        interval_seconds = int(self.interval.total_seconds())
        epoch_seconds = int(timestamp.timestamp())
        bucket = epoch_seconds - epoch_seconds % interval_seconds
        return datetime.fromtimestamp(bucket, tz=timestamp.tzinfo)
