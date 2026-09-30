import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

RESEARCH_BOUNDARIES_VERSION = 1
WALK_FORWARD_SPEC_VERSION = 1


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


@dataclass(frozen=True, slots=True)
class WalkForwardSpec:
    train_length: timedelta
    test_length: timedelta
    step: timedelta
    embargo: timedelta = timedelta(0)
    version: int = WALK_FORWARD_SPEC_VERSION

    def __post_init__(self) -> None:
        if self.version != WALK_FORWARD_SPEC_VERSION:
            raise ValueError("unsupported walk-forward specification version")
        if self.train_length <= timedelta(0):
            raise ValueError("train_length must be positive")
        if self.test_length <= timedelta(0):
            raise ValueError("test_length must be positive")
        if self.step <= timedelta(0):
            raise ValueError("step must be positive")
        if self.embargo < timedelta(0):
            raise ValueError("embargo must be non-negative")

    @property
    def spec_id(self) -> str:
        return (
            f"walk_forward_v{self.version}_"
            f"train{_timedelta_microseconds(self.train_length)}_"
            f"test{_timedelta_microseconds(self.test_length)}_"
            f"step{_timedelta_microseconds(self.step)}_"
            f"embargo{_timedelta_microseconds(self.embargo)}"
        )


@dataclass(frozen=True, slots=True)
class WalkForwardFold:
    index: int
    train: ResearchWindow
    test: ResearchWindow
    spec_id: str

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("fold index must be non-negative")
        if not self.spec_id:
            raise ValueError("spec_id must not be empty")
        if self.train.end > self.test.start:
            raise ValueError("walk-forward train and test windows must not overlap")



def generate_walk_forward_folds(
    universe: ResearchWindow,
    *,
    spec: WalkForwardSpec,
) -> tuple[WalkForwardFold, ...]:
    folds: list[WalkForwardFold] = []
    train_start = universe.start
    index = 0

    while True:
        train_end = train_start + spec.train_length
        test_start = train_end + spec.embargo
        test_end = test_start + spec.test_length
        if test_end > universe.end:
            break
        folds.append(
            WalkForwardFold(
                index=index,
                train=ResearchWindow(start=train_start, end=train_end),
                test=ResearchWindow(start=test_start, end=test_end),
                spec_id=spec.spec_id,
            )
        )
        train_start += spec.step
        index += 1

    return tuple(folds)


def _window_payload(window: ResearchWindow) -> dict[str, str]:
    return {
        "start": window.start.astimezone(UTC).isoformat(),
        "end": window.end.astimezone(UTC).isoformat(),
    }


def _timedelta_microseconds(value: timedelta) -> int:
    return (value.days * 86_400 + value.seconds) * 1_000_000 + value.microseconds


def _require_aware(timestamp: datetime, name: str) -> None:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
