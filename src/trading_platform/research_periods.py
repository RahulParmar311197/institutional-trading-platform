import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

RESEARCH_BOUNDARIES_VERSION = 1


class DatasetPartition(StrEnum):
    TRAIN = "TRAIN"
    VALIDATION = "VALIDATION"
    TEST = "TEST"


@dataclass(frozen=True, slots=True)
class ResearchWindow:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        _require_aware(self.start, "start")
        _require_aware(self.end, "end")
        if self.start >= self.end:
            raise ValueError("research window start must be before end")

    def contains(self, timestamp: datetime) -> bool:
        _require_aware(timestamp, "timestamp")
        return self.start <= timestamp < self.end


@dataclass(frozen=True, slots=True)
class ResearchDatasetBoundaries:
    train: ResearchWindow
    test: ResearchWindow
    validation: ResearchWindow | None = None
    version: int = RESEARCH_BOUNDARIES_VERSION

    def __post_init__(self) -> None:
        if self.version != RESEARCH_BOUNDARIES_VERSION:
            raise ValueError("unsupported research-boundaries version")
        if self.validation is None:
            if self.train.end > self.test.start:
                raise ValueError("train and test windows must not overlap")
            return
        if self.train.end > self.validation.start:
            raise ValueError("train and validation windows must not overlap")
        if self.validation.end > self.test.start:
            raise ValueError("validation and test windows must not overlap")

    @property
    def boundary_id(self) -> str:
        payload = {
            "version": self.version,
            "train": _window_payload(self.train),
            "validation": (
                _window_payload(self.validation) if self.validation is not None else None
            ),
            "test": _window_payload(self.test),
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        return f"research_boundaries_v{self.version}_{hashlib.sha256(encoded).hexdigest()}"

    def partition_for(self, timestamp: datetime) -> DatasetPartition | None:
        _require_aware(timestamp, "timestamp")
        if self.train.contains(timestamp):
            return DatasetPartition.TRAIN
        if self.validation is not None and self.validation.contains(timestamp):
            return DatasetPartition.VALIDATION
        if self.test.contains(timestamp):
            return DatasetPartition.TEST
        return None


def _window_payload(window: ResearchWindow) -> dict[str, str]:
    return {
        "start": window.start.isoformat(),
        "end": window.end.isoformat(),
    }


def _require_aware(timestamp: datetime, name: str) -> None:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
