import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from trading_platform.research_periods import WalkForwardFold
from trading_platform.research_results import OOSBacktestResult, OOSProvenance

WALK_FORWARD_REPORT_VERSION = 1


@dataclass(frozen=True, slots=True)
class WalkForwardFoldResult:
    fold: WalkForwardFold
    result: OOSBacktestResult

    def __post_init__(self) -> None:
        provenance = self.result.provenance
        if provenance.fold_id != self.fold.fold_id:
            raise ValueError("OOS result fold_id does not match walk-forward fold")
        if provenance.fold_spec_id != self.fold.spec_id:
            raise ValueError("OOS result fold_spec_id does not match walk-forward fold")


@dataclass(frozen=True, slots=True)
class WalkForwardFoldSummary:
    index: int
    fold_id: str
    result_id: str
    test_start: datetime
    test_end: datetime
    total_return: Decimal
    max_drawdown_pct: Decimal
    trade_count: int
    rejected_decisions: int


@dataclass(frozen=True, slots=True)
class WalkForwardReport:
    boundary_id: str
    fold_spec_id: str
    strategy_id: str
    feature_ids: tuple[str, ...]
    backtest_config_digest: str
    slippage_bps: Decimal
    fee_per_filled_order: Decimal
    folds: tuple[WalkForwardFoldSummary, ...]
    mean_fold_total_return: Decimal
    version: int = WALK_FORWARD_REPORT_VERSION

    def __post_init__(self) -> None:
        if self.version != WALK_FORWARD_REPORT_VERSION:
            raise ValueError("unsupported walk-forward report version")
        if not self.folds:
            raise ValueError("walk-forward report requires at least one fold summary")

    @property
    def report_id(self) -> str:
        payload = {
            "version": self.version,
            "boundary_id": self.boundary_id,
            "fold_spec_id": self.fold_spec_id,
            "strategy_id": self.strategy_id,
            "feature_ids": self.feature_ids,
            "backtest_config_digest": self.backtest_config_digest,
            "slippage_bps": _decimal_identity(self.slippage_bps),
            "fee_per_filled_order": _decimal_identity(self.fee_per_filled_order),
            "mean_fold_total_return": _decimal_identity(self.mean_fold_total_return),
            "folds": [
                {
                    "index": fold.index,
                    "fold_id": fold.fold_id,
                    "result_id": fold.result_id,
                    "test_start": _datetime_identity(fold.test_start),
                    "test_end": _datetime_identity(fold.test_end),
                    "total_return": _decimal_identity(fold.total_return),
                    "max_drawdown_pct": _decimal_identity(fold.max_drawdown_pct),
                    "trade_count": fold.trade_count,
                    "rejected_decisions": fold.rejected_decisions,
                }
                for fold in self.folds
            ],
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        return f"walk_forward_report_v{self.version}_{hashlib.sha256(encoded).hexdigest()}"


def build_walk_forward_report(
    evaluations: tuple[WalkForwardFoldResult, ...],
) -> WalkForwardReport:
    if not evaluations:
        raise ValueError("walk-forward report requires at least one fold result")

    expected_indexes = tuple(range(len(evaluations)))
    actual_indexes = tuple(evaluation.fold.index for evaluation in evaluations)
    if actual_indexes != expected_indexes:
        raise ValueError("walk-forward fold results must be ordered and contiguous from index 0")

    first = evaluations[0].result.provenance
    previous_test_start: datetime | None = None
    summaries: list[WalkForwardFoldSummary] = []
    total_return_sum = Decimal("0")

    for evaluation in evaluations:
        fold = evaluation.fold
        result = evaluation.result
        provenance = result.provenance
        _require_compatible(first, provenance)
        if previous_test_start is not None and fold.test.start <= previous_test_start:
            raise ValueError("walk-forward fold test windows must advance in time")
        previous_test_start = fold.test.start

        metrics = result.result.metrics
        summaries.append(
            WalkForwardFoldSummary(
                index=fold.index,
                fold_id=fold.fold_id,
                result_id=result.result_id,
                test_start=fold.test.start,
                test_end=fold.test.end,
                total_return=metrics.total_return,
                max_drawdown_pct=metrics.max_drawdown_pct,
                trade_count=metrics.trade_count,
                rejected_decisions=result.result.rejected_decisions,
            )
        )
        total_return_sum += metrics.total_return

    return WalkForwardReport(
        boundary_id=first.boundary_id,
        fold_spec_id=first.fold_spec_id,
        strategy_id=first.strategy_id,
        feature_ids=first.feature_ids,
        backtest_config_digest=first.backtest_config_digest,
        slippage_bps=first.slippage_bps,
        fee_per_filled_order=first.fee_per_filled_order,
        folds=tuple(summaries),
        mean_fold_total_return=total_return_sum / Decimal(len(summaries)),
    )


def _require_compatible(
    reference: OOSProvenance,
    candidate: OOSProvenance,
) -> None:
    fields = (
        "boundary_id",
        "fold_spec_id",
        "strategy_id",
        "feature_ids",
        "backtest_config_digest",
        "slippage_bps",
        "fee_per_filled_order",
        "version",
    )
    for field in fields:
        if getattr(reference, field) != getattr(candidate, field):
            raise ValueError(f"incompatible OOS fold provenance: {field}")


def _datetime_identity(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _decimal_identity(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == 0:
        return "0"
    return format(normalized, "f")
