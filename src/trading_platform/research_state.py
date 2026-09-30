import hashlib
import json
from dataclasses import dataclass
from datetime import UTC
from enum import StrEnum

from trading_platform.recorded_events import RecordedMarketEvent, normalize_recorded_events
from trading_platform.replay import ReplayStream
from trading_platform.research_periods import ResearchWindow, WalkForwardFold

RESEARCH_STATE_PROVENANCE_VERSION = 1


class ResearchStateKind(StrEnum):
    WARMUP = "WARMUP"
    FITTED = "FITTED"


@dataclass(frozen=True, slots=True)
class ResearchStateProvenance:
    kind: ResearchStateKind
    boundary_id: str
    fold_id: str
    fold_spec_id: str
    strategy_id: str
    feature_ids: tuple[str, ...]
    source_window: ResearchWindow
    source_stream_digest: str
    state_digest: str
    version: int = RESEARCH_STATE_PROVENANCE_VERSION

    def __post_init__(self) -> None:
        if self.version != RESEARCH_STATE_PROVENANCE_VERSION:
            raise ValueError("unsupported research-state provenance version")
        for name, value in (
            ("boundary_id", self.boundary_id),
            ("fold_id", self.fold_id),
            ("fold_spec_id", self.fold_spec_id),
            ("strategy_id", self.strategy_id),
        ):
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        if len(set(self.feature_ids)) != len(self.feature_ids):
            raise ValueError("feature_ids must not contain duplicates")
        if any(not feature_id.strip() for feature_id in self.feature_ids):
            raise ValueError("feature_ids must not contain empty values")
        _validate_digest(self.source_stream_digest, "source_stream_digest")
        _validate_digest(self.state_digest, "state_digest")

    @property
    def provenance_id(self) -> str:
        payload = {
            "version": self.version,
            "kind": self.kind.value,
            "boundary_id": self.boundary_id,
            "fold_id": self.fold_id,
            "fold_spec_id": self.fold_spec_id,
            "strategy_id": self.strategy_id,
            "feature_ids": self.feature_ids,
            "source_window": {
                "start": self.source_window.start.astimezone(UTC).isoformat(),
                "end": self.source_window.end.astimezone(UTC).isoformat(),
            },
            "source_stream_digest": self.source_stream_digest,
            "state_digest": self.state_digest,
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        return (
            f"research_state_v{self.version}_"
            f"{hashlib.sha256(encoded).hexdigest()}"
        )

    @classmethod
    def from_events(
        cls,
        *,
        kind: ResearchStateKind,
        boundary_id: str,
        fold: WalkForwardFold,
        strategy_id: str,
        feature_ids: tuple[str, ...],
        source_window: ResearchWindow,
        source_events: list[RecordedMarketEvent],
        serialized_state: bytes,
    ) -> "ResearchStateProvenance":
        _validate_source_window(kind=kind, fold=fold, source_window=source_window)
        if not serialized_state:
            raise ValueError("serialized research state must not be empty")

        normalized = normalize_recorded_events(source_events)
        if not normalized:
            raise ValueError("research state provenance requires source events")
        if any(
            not source_window.contains(event.exchange_timestamp)
            for event in normalized
        ):
            raise ValueError("research state source events must be confined to source_window")

        return cls(
            kind=kind,
            boundary_id=boundary_id,
            fold_id=fold.fold_id,
            fold_spec_id=fold.spec_id,
            strategy_id=strategy_id,
            feature_ids=feature_ids,
            source_window=source_window,
            source_stream_digest=ReplayStream(events=normalized).stream_digest,
            state_digest=hashlib.sha256(serialized_state).hexdigest(),
        )


def _validate_source_window(
    *,
    kind: ResearchStateKind,
    fold: WalkForwardFold,
    source_window: ResearchWindow,
) -> None:
    if kind is ResearchStateKind.FITTED:
        if source_window != fold.train:
            raise ValueError("fitted state source_window must equal the fold train window")
        return

    if source_window.start < fold.train.start or source_window.end > fold.train.end:
        raise ValueError("warmup state source_window must be contained in the fold train window")
    if source_window.end != fold.train.end:
        raise ValueError("warmup state source_window must end at the fold train boundary")


def _validate_digest(value: str, name: str) -> None:
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
