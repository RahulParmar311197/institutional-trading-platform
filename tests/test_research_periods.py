from datetime import UTC, datetime, timedelta, timezone

import pytest

from trading_platform.research_periods import (
    DatasetPartition,
    ResearchDatasetBoundaries,
    ResearchWindow,
    WalkForwardSpec,
    generate_walk_forward_folds,
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


def test_walk_forward_folds_are_rolling_half_open_and_deterministic() -> None:
    spec = WalkForwardSpec(
        train_length=timedelta(days=10),
        test_length=timedelta(days=2),
        step=timedelta(days=2),
    )

    folds = generate_walk_forward_folds(window(0, 16), spec=spec)

    assert len(folds) == 3
    assert [(fold.train.start, fold.train.end) for fold in folds] == [
        (BASE, BASE + timedelta(days=10)),
        (BASE + timedelta(days=2), BASE + timedelta(days=12)),
        (BASE + timedelta(days=4), BASE + timedelta(days=14)),
    ]
    assert [(fold.test.start, fold.test.end) for fold in folds] == [
        (BASE + timedelta(days=10), BASE + timedelta(days=12)),
        (BASE + timedelta(days=12), BASE + timedelta(days=14)),
        (BASE + timedelta(days=14), BASE + timedelta(days=16)),
    ]
    assert [fold.index for fold in folds] == [0, 1, 2]
    assert {fold.spec_id for fold in folds} == {spec.spec_id}
    assert len({fold.fold_id for fold in folds}) == 3
    assert all(fold.fold_id.startswith("walk_forward_fold_") for fold in folds)


def test_walk_forward_fold_identity_is_timezone_canonical() -> None:
    spec = WalkForwardSpec(
        train_length=timedelta(days=5),
        test_length=timedelta(days=2),
        step=timedelta(days=1),
    )
    fold = generate_walk_forward_folds(window(0, 7), spec=spec)[0]
    plus_one = timezone(timedelta(hours=1))
    shifted = type(fold)(
        index=fold.index,
        train=ResearchWindow(
            start=fold.train.start.astimezone(plus_one),
            end=fold.train.end.astimezone(plus_one),
        ),
        test=ResearchWindow(
            start=fold.test.start.astimezone(plus_one),
            end=fold.test.end.astimezone(plus_one),
        ),
        spec_id=fold.spec_id,
    )

    assert fold.fold_id == shifted.fold_id


def test_walk_forward_embargo_separates_training_and_test_data() -> None:
    spec = WalkForwardSpec(
        train_length=timedelta(days=5),
        test_length=timedelta(days=2),
        step=timedelta(days=2),
        embargo=timedelta(days=1),
    )

    folds = generate_walk_forward_folds(window(0, 10), spec=spec)

    assert len(folds) == 2
    assert folds[0].train.end == BASE + timedelta(days=5)
    assert folds[0].test.start == BASE + timedelta(days=6)
    assert folds[0].test.end == BASE + timedelta(days=8)
    assert folds[1].train.start == BASE + timedelta(days=2)
    assert folds[1].test.end == BASE + timedelta(days=10)


def test_walk_forward_does_not_emit_truncated_final_fold() -> None:
    spec = WalkForwardSpec(
        train_length=timedelta(days=5),
        test_length=timedelta(days=3),
        step=timedelta(days=3),
    )

    folds = generate_walk_forward_folds(window(0, 10), spec=spec)

    assert len(folds) == 1
    assert folds[0].test.end == BASE + timedelta(days=8)


def test_walk_forward_spec_identity_and_validation_are_explicit() -> None:
    spec = WalkForwardSpec(
        train_length=timedelta(days=5),
        test_length=timedelta(days=2),
        step=timedelta(days=1),
        embargo=timedelta(hours=12),
    )

    assert spec.spec_id == (
        "walk_forward_v1_train432000000000_test172800000000_"
        "step86400000000_embargo43200000000"
    )

    with pytest.raises(ValueError, match="train_length"):
        WalkForwardSpec(
            train_length=timedelta(0),
            test_length=timedelta(days=1),
            step=timedelta(days=1),
        )
    with pytest.raises(ValueError, match="test_length"):
        WalkForwardSpec(
            train_length=timedelta(days=1),
            test_length=timedelta(0),
            step=timedelta(days=1),
        )
    with pytest.raises(ValueError, match="step"):
        WalkForwardSpec(
            train_length=timedelta(days=1),
            test_length=timedelta(days=1),
            step=timedelta(0),
        )
    with pytest.raises(ValueError, match="embargo"):
        WalkForwardSpec(
            train_length=timedelta(days=1),
            test_length=timedelta(days=1),
            step=timedelta(days=1),
            embargo=-timedelta(seconds=1),
        )
