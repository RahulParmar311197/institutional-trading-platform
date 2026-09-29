from dataclasses import dataclass, field

from trading_platform.recorded_events import RecordedMarketEvent, normalize_recorded_events


@dataclass(slots=True)
class ReplayStream:
    events: tuple[RecordedMarketEvent, ...]
    _cursor: int = field(default=0, init=False)

    @classmethod
    def from_events(cls, events: list[RecordedMarketEvent]) -> "ReplayStream":
        return cls(events=normalize_recorded_events(events))

    @property
    def cursor(self) -> int:
        return self._cursor

    @property
    def remaining(self) -> int:
        return len(self.events) - self._cursor

    def reset(self) -> None:
        self._cursor = 0

    def next_event(self) -> RecordedMarketEvent | None:
        if self._cursor >= len(self.events):
            return None
        event = self.events[self._cursor]
        self._cursor += 1
        return event

    def step(self, count: int = 1) -> tuple[RecordedMarketEvent, ...]:
        if count <= 0:
            raise ValueError("count must be positive")
        start = self._cursor
        end = min(start + count, len(self.events))
        self._cursor = end
        return self.events[start:end]
