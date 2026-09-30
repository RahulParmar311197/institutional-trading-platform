import hashlib
import json
import os
import tempfile
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path

from trading_platform.recorded_events import RecordedMarketEvent, normalize_recorded_events

REPLAY_CHECKPOINT_VERSION = 1
REPLAY_CHECKPOINT_FIELDS = frozenset(
    {"version", "cursor", "event_count", "stream_digest"}
)
REPLAY_CHECKPOINT_MAX_BYTES = 4096


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

    def to_json(self) -> str:
        return json.dumps(
            {
                "version": self.version,
                "cursor": self.cursor,
                "event_count": self.event_count,
                "stream_digest": self.stream_digest,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, payload: str) -> "ReplayCheckpoint":
        try:
            raw = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid replay checkpoint JSON") from exc
        if not isinstance(raw, dict):
            raise ValueError("replay checkpoint JSON must be an object")
        if frozenset(raw) != REPLAY_CHECKPOINT_FIELDS:
            raise ValueError("replay checkpoint JSON has unexpected fields")
        if type(raw["version"]) is not int:
            raise ValueError("checkpoint version must be an integer")
        if type(raw["cursor"]) is not int:
            raise ValueError("checkpoint cursor must be an integer")
        if type(raw["event_count"]) is not int:
            raise ValueError("checkpoint event_count must be an integer")
        if not isinstance(raw["stream_digest"], str):
            raise ValueError("checkpoint stream_digest must be a string")
        return cls(
            version=raw["version"],
            cursor=raw["cursor"],
            event_count=raw["event_count"],
            stream_digest=raw["stream_digest"],
        )


class ReplayCheckpointFileStore:
    """Atomic local persistence for replay checkpoints.

    This store persists cursor identity only. It does not make processing side effects
    exactly-once and must not be used as a substitute for transactional execution state.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if not self.path.name:
            raise ValueError("checkpoint path must name a file")

    def load(self) -> ReplayCheckpoint | None:
        try:
            with self.path.open("rb") as handle:
                payload = handle.read(REPLAY_CHECKPOINT_MAX_BYTES + 1)
        except FileNotFoundError:
            return None
        if len(payload) > REPLAY_CHECKPOINT_MAX_BYTES:
            raise ValueError("replay checkpoint file exceeds maximum size")
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("replay checkpoint file must be valid UTF-8") from exc
        return ReplayCheckpoint.from_json(text)

    def save(self, checkpoint: ReplayCheckpoint) -> None:
        payload = (checkpoint.to_json() + "\n").encode("utf-8")
        if len(payload) > REPLAY_CHECKPOINT_MAX_BYTES:
            raise ValueError("replay checkpoint exceeds maximum size")

        parent = self.path.parent
        parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=parent,
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, self.path)
            _fsync_directory(parent)
        except BaseException:
            with suppress(FileNotFoundError):
                os.unlink(temporary_name)
            raise

    def clear(self) -> bool:
        try:
            self.path.unlink()
        except FileNotFoundError:
            return False
        _fsync_directory(self.path.parent)
        return True


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


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    directory_fd = os.open(path, flags)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


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
