import hashlib
import json
from dataclasses import dataclass, field

from trading_platform.recorded_events import RecordedMarketEvent, normalize_recorded_events

REPLAY_CHECKPOINT_VERSION = 1


@dataclass(frozen=True, slots=True)
class ReplayCheckpoint:
    cursor: int
    event_count: int
    stream_digest: str
    version: int = REPLAY_CHECKPOINT_VERSION

    def __post_init__(self) -> None:
        if self.version != REPLAY_CHECKPOINT_VERSION:
            raise ValueError("unsupported replay checkpoint version")
        if self.cursor < 0:
            raise ValueError("checkpoint cursor must be non-negative")
        if self.event_count < 0:
            raise ValueError("checkpoint event_count must be non-negative")
        if self.cursor > self.event_count:
            raise ValueError("checkpoint cursor must not exceed event_count")
        if len(self.stream_digest) != 64 or any(
            character not in "0123456789abcdef" for character in self.stream_digest
        ):
            raise ValueError("checkpoint stream_digest must be a lowercase SHA-256 hex digest")


@dataclass(slots=True)
class ReplayStream:
    events: tuple[RecordedMarketEvent, ...]
    _cursor: int = field(default=0, init=False)
    _stream_digest: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._stream_digest = _digest_events(self.events)

    @classmethod
    def from_events(cls, events: list[RecordedMarketEvent]) -> "ReplayStream":
        return cls(events=normalize_recorded_events(events))

    @property
    def cursor(self) -> int:
        return self._cursor

    @property
    def remaining(self) -> int:
        return len(self.events) - self._cursor

    @property
    def stream_digest(self) -> str:
        return self._stream_digest

    def reset(self) -> None:
        self._cursor = 0

    def checkpoint(self) -> ReplayCheckpoint:
        return ReplayCheckpoint(
            cursor=self._cursor,
            event_count=len(self.events),
            stream_digest=self._stream_digest,
        )

    def restore(self, checkpoint: ReplayCheckpoint) -> None:
        if checkpoint.event_count != len(self.events):
            raise ValueError("replay checkpoint event count does not match stream")
        if checkpoint.stream_digest != self._stream_digest:
            raise ValueError("replay checkpoint stream digest does not match stream")
        self._cursor = checkpoint.cursor

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


def _digest_events(events: tuple[RecordedMarketEvent, ...]) -> str:
    payload = [
        {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "instrument_id": str(event.instrument_id),
            "source": event.source,
            "exchange_timestamp": event.exchange_timestamp.isoformat(),
            "provider_timestamp": (
                event.provider_timestamp.isoformat()
                if event.provider_timestamp is not None
                else None
            ),
            "ingestion_timestamp": event.ingestion_timestamp.isoformat(),
            "sequence": event.sequence,
            "price": str(event.price),
            "quantity": event.quantity,
        }
        for event in events
    ]
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
