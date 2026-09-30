import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from trading_platform.research_grid import EmaGridSelectedWarmOOSResult
from trading_platform.research_periods import WalkForwardFold

EMA_GRID_OOS_REPORT_VERSION = 1


@dataclass(frozen=True, slots=True)
class EmaGridOOSFoldResult:
    fold: WalkForwardFold
    result: EmaGridSelectedWarmOOSResult

    def __post_init__(self) -> None:
        provenance = self.result.selected_warm.oos.provenance
        if provenance.fold_id != self.fold.fold_id:
            raise ValueError("grid OOS result fold_id does not match walk-forward fold")
        if provenance.fold_spec_id != self.fold.spec_id:
            raise ValueError("grid OOS result fold_spec_id does not match walk-forward fold")


@dataclass(frozen=True, slots=True)
class EmaGridOOSFoldSummary:
    index: int
    fold_id: str
    grid_id: str
    search_id: str
    selection_decision_id: str
    candidate_id: str
    preparation_state_id: str
    result_id: str
    test_start: datetime
    test_end: datetime
    total_return: Decimal
    max_drawdown_pct: Decimal
    trade_count: int
    rejected_decisions: int


@dataclass(frozen=True, slots=True)
class EmaGridOOSReport:
    boundary_id: str
    fold_spec_id: str
    grid_id: str
    feature_ids: tuple[str, ...]
    slippage_bps: Decimal
    fee_per_filled_order: Decimal
    folds: tuple[EmaGridOOSFoldSummary, ...]
    mean_fold_total_return: Decimal
    version: int = EMA_GRID_OOS_REPORT_VERSION

    def __post_init__(self) -> None:
        if self.version != EMA_GRID_OOS_REPORT_VERSION:
            raise ValueError("unsupported EMA grid OOS report version")
        if not self.folds:
            raise ValueError("EMA grid OOS report requires fold summaries")

    @property
    def report_id(self) -> str:
        payload = {
            "version": self.version,
            "boundary_id": self.boundary_id,
            "fold_spec_id": self.fold_spec_id,
            "grid_id": self.grid_id,
            "feature_ids": self.feature_ids,
            "slippage_bps": _decimal_identity(self.slippage_bps),
            "fee_per_filled_order": _decimal_identity(self.fee_per_filled_order),
            "mean_fold_total_return": _decimal_identity(self.mean_fold_total_return),
            "folds": [
                {
                    "index": fold.index,
                    "fold_id": fold.fold_id,
                    "grid_id": fold.grid_id,
                    "search_id": fold.search_id,
                    "selection_decision_id": fold.selection_decision_id,
                    "candidate_id": fold.candidate_id,
                    "preparation_state_id": fold.preparation_state_id,
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
        return f"ema_grid_oos_report_v{self.version}_{hashlib.sha256(encoded).hexdigest()}"


def build_ema_grid_oos_report(
    evaluations: tuple[EmaGridOOSFoldResult, ...],
) -> EmaGridOOSReport:
    if not evaluations:
        raise ValueError("EMA grid OOS report requires fold results")
    indexes = tuple(item.fold.index for item in evaluations)
    if indexes != tuple(range(len(evaluations))):
        raise ValueError("EMA grid OOS fold results must be ordered and contiguous from index 0")

    first_result = evaluations[0].result
    first_provenance = first_result.selected_warm.oos.provenance
    grid_id = first_result.grid_id
    previous_test_start: datetime | None = None
    summaries: list[EmaGridOOSFoldSummary] = []
    total_return_sum = Decimal("0")

    for evaluation in evaluations:
        fold = evaluation.fold
        envelope = evaluation.result
        provenance = envelope.selected_warm.oos.provenance
        if envelope.grid_id != grid_id:
            raise ValueError("EMA grid OOS fold results must share one grid_id")
        for field in (
            "boundary_id",
            "fold_spec_id",
            "feature_ids",
            "slippage_bps",
            "fee_per_filled_order",
            "version",
        ):
            if getattr(provenance, field) != getattr(first_provenance, field):
                raise ValueError(f"incompatible EMA grid OOS fold provenance: {field}")
        if previous_test_start is not None and fold.test.start <= previous_test_start:
            raise ValueError("EMA grid OOS fold test windows must advance in time")
        previous_test_start = fold.test.start

        metrics = envelope.selected_warm.oos.result.metrics
        summaries.append(
            EmaGridOOSFoldSummary(
                index=fold.index,
                fold_id=fold.fold_id,
                grid_id=envelope.grid_id,
                search_id=envelope.search_id,
                selection_decision_id=envelope.selected_warm.selection_decision_id,
                candidate_id=envelope.selected_warm.candidate_id,
                preparation_state_id=envelope.selected_warm.preparation_state_id,
                result_id=envelope.result_id,
                test_start=fold.test.start,
                test_end=fold.test.end,
                total_return=metrics.total_return,
                max_drawdown_pct=metrics.max_drawdown_pct,
                trade_count=metrics.trade_count,
                rejected_decisions=envelope.selected_warm.oos.result.rejected_decisions,
            )
        )
        total_return_sum += metrics.total_return

    return EmaGridOOSReport(
        boundary_id=first_provenance.boundary_id,
        fold_spec_id=first_provenance.fold_spec_id,
        grid_id=grid_id,
        feature_ids=first_provenance.feature_ids,
        slippage_bps=first_provenance.slippage_bps,
        fee_per_filled_order=first_provenance.fee_per_filled_order,
        folds=tuple(summaries),
        mean_fold_total_return=total_return_sum / Decimal(len(summaries)),
    )


def _datetime_identity(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _decimal_identity(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == 0:
        return "0"
    return format(normalized, "f")
