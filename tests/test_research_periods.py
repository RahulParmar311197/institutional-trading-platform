from datetime import UTC, datetime, timedelta, timezone

import pytest

from trading_platform.research_periods import (
    DatasetPartition,
    ResearchDatasetBoundaries,
    ResearchWindow,
)

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def window(start_day: int, end_day: int) -> ResearchWindow:
    return ResearchWindow(
        start=BASE + timedelta(days=start_day),
        end=BASE + timedelta(days=end_day),
    )


def test_dataset_boundaries_are_half_open_and_leave_gaps_unassigned() -> None:
    boundaries = ResearchDatasetBoundaries(
        train=window(0, 10),
        validation=window(12, 15),
        test=window(20, 25),
    )

    assert boundaries.partition_for(BASE) is DatasetPartition.TRAIN
    assert boundaries.partition_for(BASE + timedelta(days=9, hours=23)) is DatasetPartition.TRAIN
    assert boundaries.partition_for(BASE + timedelta(days=10)) is None
    assert boundaries.partition_for(BASE + timedelta(days=12)) is DatasetPartition.VALIDATION
    assert boundaries.partition_for(BASE + timedelta(days=15)) is None
    assert boundaries.partition_for(BASE + timedelta(days=20)) is DatasetPartition.TEST
    assert boundaries.partition_for(BASE + timedelta(days=25)) is None


def test_dataset_boundaries_reject_overlap_across_partitions() -> None:
    with pytest.raises(ValueError, match="train and validation"):
        ResearchDatasetBoundaries(
            train=window(0, 10),
            validation=window(9, 12),
            test=window(12, 15),
        )

    with pytest.raises(ValueError, match="validation and test"):
        ResearchDatasetBoundaries(
            train=window(0, 10),
            validation=window(10, 13),
            test=window(12, 15),
        )

    with pytest.raises(ValueError, match="train and test"):
        ResearchDatasetBoundaries(
            train=window(0, 10),
            test=window(9, 15),
        )


def test_boundary_identity_is_versioned_and_canonical_across_timezones() -> None:
    utc_boundaries = ResearchDatasetBoundaries(train=window(0, 10), test=window(10, 20))
    plus_one = timezone(timedelta(hours=1))
    shifted_representation = ResearchDatasetBoundaries(
        train=ResearchWindow(
            start=utc_boundaries.train.start.astimezone(plus_one),
            end=utc_boundaries.train.end.astimezone(plus_one),
        ),
        test=ResearchWindow(
            start=utc_boundaries.test.start.astimezone(plus_one),
            end=utc_boundaries.test.end.astimezone(plus_one),
        ),
    )

    assert utc_boundaries.boundary_id.startswith("research_boundaries_v1_")
    assert utc_boundaries.boundary_id == shifted_representation.boundary_id


def test_research_windows_require_timezone_aware_valid_ranges() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        ResearchWindow(start=datetime(2026, 1, 1), end=datetime(2026, 1, 2))

    with pytest.raises(ValueError, match="before end"):
        ResearchWindow(start=BASE, end=BASE)

    boundaries = ResearchDatasetBoundaries(train=window(0, 10), test=window(10, 20))
    with pytest.raises(ValueError, match="timezone-aware"):
        boundaries.partition_for(datetime(2026, 1, 5))


def test_research_boundary_version_is_explicit() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        ResearchDatasetBoundaries(train=window(0, 10), test=window(10, 20), version=2)
