from dataclasses import replace
from datetime import timedelta

import pytest
from test_backtest import BASE, event, make_backtester, sample_events

from trading_platform.research_periods import ResearchWindow, WalkForwardFold
from trading_platform.research_selection import (
    ObjectiveDirection,
    SelectionSpec,
    split_fold_for_selection,
)
from trading_platform.research_validation import (
    ResearchCandidate,
    ValidationBacktestResult,
    ValidationObjective,
    evaluate_fixed_strategy_validation_fold,
    score_validation_result,
)

BOUNDARY_ID = "research_boundaries_v1_fixture"
FEATURE_IDS = ("market_regime_v1_fixture",)


def selection_fold():
    parent = WalkForwardFold(
        index=0,
        train=ResearchWindow(
            start=BASE - timedelta(minutes=10),
            end=BASE + timedelta(minutes=5),
        ),
        test=ResearchWindow(
            start=BASE + timedelta(minutes=10),
            end=BASE + timedelta(minutes=15),
        ),
        spec_id="walk_forward_v1_fixture",
    )
    return split_fold_for_selection(
        parent,
        spec=SelectionSpec(validation_length=timedelta(minutes=5)),
    )


def test_validation_evaluation_matches_direct_cold_start_backtest() -> None:
    events = sample_events()
    backtester = make_backtester()
    selection = selection_fold()

    envelope = evaluate_fixed_strategy_validation_fold(
        backtester,
        events,
        boundary_id=BOUNDARY_ID,
        selection_fold=selection,
        feature_ids=FEATURE_IDS,
    )

    assert envelope.result == backtester.run(events)
    assert envelope.provenance.selection_fold_id == selection.selection_fold_id
    assert envelope.candidate.strategy_id == backtester.strategy.strategy_id
    assert envelope.candidate.feature_ids == FEATURE_IDS
    assert envelope.provenance.candidate_id == envelope.candidate.candidate_id
    assert envelope.result_id.startswith("validation_result_v1_")


def test_validation_evaluation_rejects_fit_or_test_event_leakage() -> None:
    selection = selection_fold()
    fit_timestamp = selection.fit.end - timedelta(minutes=1)
    leaked_fit = replace(
        event("fit-leak", 0, "100"),
        exchange_timestamp=fit_timestamp,
        provider_timestamp=fit_timestamp,
        ingestion_timestamp=fit_timestamp,
    )

    with pytest.raises(ValueError, match="confined to the validation window"):
        evaluate_fixed_strategy_validation_fold(
            make_backtester(),
            [leaked_fit, *sample_events()],
            boundary_id=BOUNDARY_ID,
            selection_fold=selection,
        )

    test_timestamp = selection.test.start
    leaked_test = replace(
        event("test-leak", 0, "100"),
        exchange_timestamp=test_timestamp,
        provider_timestamp=test_timestamp,
        ingestion_timestamp=test_timestamp,
    )
    with pytest.raises(ValueError, match="confined to the validation window"):
        evaluate_fixed_strategy_validation_fold(
            make_backtester(),
            [*sample_events(), leaked_test],
            boundary_id=BOUNDARY_ID,
            selection_fold=selection,
        )


def test_validation_candidate_identity_binds_configuration_and_features() -> None:
    backtester = make_backtester()
    candidate = ResearchCandidate.from_backtester(backtester, feature_ids=FEATURE_IDS)
    equivalent = ResearchCandidate.from_backtester(backtester, feature_ids=FEATURE_IDS)
    changed_features = ResearchCandidate.from_backtester(
        backtester,
        feature_ids=("market_regime_v2_fixture",),
    )

    assert candidate.candidate_id == equivalent.candidate_id
    assert candidate.candidate_id != changed_features.candidate_id
    assert candidate.candidate_id.startswith("research_candidate_v1_")


def test_validation_score_is_derived_from_bound_result_and_objective() -> None:
    envelope = evaluate_fixed_strategy_validation_fold(
        make_backtester(),
        sample_events(),
        boundary_id=BOUNDARY_ID,
        selection_fold=selection_fold(),
        feature_ids=FEATURE_IDS,
    )

    total_return = score_validation_result(
        envelope,
        objective=ValidationObjective.TOTAL_RETURN,
    )
    drawdown = score_validation_result(
        envelope,
        objective=ValidationObjective.MAX_DRAWDOWN_PCT,
    )

    assert total_return.validation_result_id == envelope.result_id
    assert total_return.candidate_id == envelope.candidate.candidate_id
    assert total_return.objective_id == "total_return_v1"
    assert total_return.direction is ObjectiveDirection.MAXIMIZE
    assert total_return.score == envelope.result.metrics.total_return
    assert drawdown.objective_id == "max_drawdown_pct_v1"
    assert drawdown.direction is ObjectiveDirection.MINIMIZE
    assert drawdown.score == envelope.result.metrics.max_drawdown_pct


def test_validation_result_rejects_candidate_provenance_mismatch() -> None:
    envelope = evaluate_fixed_strategy_validation_fold(
        make_backtester(),
        sample_events(),
        boundary_id=BOUNDARY_ID,
        selection_fold=selection_fold(),
    )
    changed = replace(
        envelope.candidate,
        feature_ids=("different-feature",),
    )

    with pytest.raises(ValueError, match="does not match candidate"):
        ValidationBacktestResult(
            candidate=changed,
            provenance=envelope.provenance,
            result=envelope.result,
        )
