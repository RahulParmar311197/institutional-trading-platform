from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True, slots=True)
class TradingSession:
    timezone: ZoneInfo
    open_time: time
    close_time: time

    def bounds_for(self, timestamp: datetime) -> tuple[datetime, datetime]:
        local = timestamp.astimezone(self.timezone)
        session_open = datetime.combine(local.date(), self.open_time, self.timezone)
        session_close = datetime.combine(local.date(), self.close_time, self.timezone)
        if session_close <= session_open:
            raise ValueError("session close must be after session open")
        return session_open, session_close

    def contains(self, timestamp: datetime) -> bool:
        session_open, session_close = self.bounds_for(timestamp)
        local = timestamp.astimezone(self.timezone)
        return session_open <= local < session_close

    def bucket_start(self, timestamp: datetime, interval: timedelta) -> datetime:
        if interval <= timedelta(0):
            raise ValueError("interval must be positive")
        session_open, session_close = self.bounds_for(timestamp)
        local = timestamp.astimezone(self.timezone)
        if not session_open <= local < session_close:
            raise ValueError("timestamp is outside the trading session")

        elapsed = local - session_open
        interval_seconds = int(interval.total_seconds())
        elapsed_seconds = int(elapsed.total_seconds())
        bucket_offset = elapsed_seconds - (elapsed_seconds % interval_seconds)
        bucket_start = session_open + timedelta(seconds=bucket_offset)
        if bucket_start >= session_close:
            raise ValueError("bucket begins after session close")
        return bucket_start.astimezone(timestamp.tzinfo)
