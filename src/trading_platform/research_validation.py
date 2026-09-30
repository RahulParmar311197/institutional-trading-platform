import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from trading_platform.backtest import BacktestResult, EventDrivenBacktester
from trading_platform.recorded_events import RecordedMarketEvent, normalize_recorded_events
from trading_platform.replay import ReplayStream
from trading_platform.research_selection import (
    ObjectiveDirection,
    SelectionFold,
    ValidationCandidateScore,
)

VALIDATION_RESULT_VERSION = 1


class ValidationObjective(StrEnum):
    TOTAL_RETURN = "total_return_v1"
    MAX_DRAWDOWN_PCT = "max_drawdown_pct_v1"

    @property
    def direction(self) -> ObjectiveDirection:
        if self is ValidationObjective.TOTAL_RETURN:
            return ObjectiveDirection.MAXIMIZE
        return ObjectiveDirection.MINIMIZE


@dataclass(frozen=True, slots=True)
class ResearchCandidate:
    strategy_id: str
    feature_ids: tuple[str, ...]
    backtest_config_digest: str
    preparation_state_id: str | None = None

    def __post_init__(self) -> None:
        if not self.strategy_id.strip():
            raise ValueError("strategy_id must not be empty")
        if len(set(self.feature_ids)) != len(self.feature_ids):
            raise ValueError("feature_ids must not contain duplicates")
        if any(not feature_id.strip() for feature_id in self.feature_ids):
            raise ValueError("feature_ids must not contain empty values")
        _validate_digest(self.backtest_config_digest, "backtest_config_digest")
        if self.preparation_state_id is not None and not self.preparation_state_id.strip():
            raise ValueError("preparation_state_id must not be empty when provided")

    @property
    def candidate_id(self) -> str:
        payload = {
            "strategy_id": self.strategy_id,
            "feature_ids": self.feature_ids,
            "backtest_config_digest": self.backtest_config_digest,
            "preparation_state_id": self.preparation_state_id,
        }
        return _identity("research_candidate_v1", payload)

    @classmethod
    def from_backtester(
        cls,
        backtester: EventDrivenBacktester,
        *,
        feature_ids: tuple[str, ...] = (),
    ) -> "ResearchCandidate":
        strategy_id = backtester.strategy.strategy_id
        if not strategy_id.strip():
            raise ValueError("validation requires a stable strategy_id")
        return cls(
            strategy_id=strategy_id,
            feature_ids=feature_ids,
            backtest_config_digest=backtester.checkpoint_config_digest(),
        )


@dataclass(frozen=True, slots=True)
class ValidationProvenance:
    boundary_id: str
    selection_fold_id: str
    candidate_id: str
    stream_digest: str
    version: int = VALIDATION_RESULT_VERSION

    def __post_init__(self) -> None:
        if self.version != VALIDATION_RESULT_VERSION:
            raise ValueError("unsupported validation result version")
        for name, value in (
            ("boundary_id", self.boundary_id),
            ("selection_fold_id", self.selection_fold_id),
            ("candidate_id", self.candidate_id),
        ):
            if not value.strip():
                raise ValueError(f"{name} must not be empty")
        _validate_digest(self.stream_digest, "stream_digest")

    @property
    def provenance_id(self) -> str:
        payload = {
            "version": self.version,
            "boundary_id": self.boundary_id,
            "selection_fold_id": self.selection_fold_id,
            "candidate_id": self.candidate_id,
            "stream_digest": self.stream_digest,
        }
        return _identity(f"validation_provenance_v{self.version}", payload)


@dataclass(frozen=True, slots=True)
class ValidationBacktestResult:
    candidate: ResearchCandidate
    provenance: ValidationProvenance
    result: BacktestResult

    def __post_init__(self) -> None:
        if self.provenance.candidate_id != self.candidate.candidate_id:
            raise ValueError("validation provenance candidate_id does not match candidate")

    @property
    def result_id(self) -> str:
        payload = {
            "provenance_id": self.provenance.provenance_id,
            "candidate_id": self.candidate.candidate_id,
            "final_position_quantity": self.result.final_position_quantity,
            "final_position_average_price": _decimal_identity(
                self.result.final_position_average_price
            ),
            "realized_pnl": _decimal_identity(self.result.realized_pnl),
            "unrealized_pnl": _decimal_identity(self.result.unrealized_pnl),
            "total_fees": _decimal_identity(self.result.total_fees),
            "net_pnl": _decimal_identity(self.result.net_pnl),
            "final_equity": _decimal_identity(self.result.final_equity),
            "rejected_decisions": self.result.rejected_decisions,
            "metrics": {
                "total_return": _decimal_identity(self.result.metrics.total_return),
                "max_drawdown": _decimal_identity(self.result.metrics.max_drawdown),
                "max_drawdown_pct": _decimal_identity(
                    self.result.metrics.max_drawdown_pct
                ),
                "trade_count": self.result.metrics.trade_count,
                "winning_realizations": self.result.metrics.winning_realizations,
                "losing_realizations": self.result.metrics.losing_realizations,
                "gross_profit": _decimal_identity(self.result.metrics.gross_profit),
                "gross_loss": _decimal_identity(self.result.metrics.gross_loss),
                "profit_factor": (
                    _decimal_identity(self.result.metrics.profit_factor)
                    if self.result.metrics.profit_factor is not None
                    else None
                ),
            },
            "trade_ids": [trade.event_id for trade in self.result.trades],
            "equity_event_ids": [point.event_id for point in self.result.equity_curve],
        }
        return _identity(f"validation_result_v{self.provenance.version}", payload)


def evaluate_fixed_strategy_validation_fold(
    backtester: EventDrivenBacktester,
    events: list[RecordedMarketEvent],
    *,
    boundary_id: str,
    selection_fold: SelectionFold,
    feature_ids: tuple[str, ...] = (),
) -> ValidationBacktestResult:
    normalized = normalize_recorded_events(events)
    if not normalized:
        raise ValueError("validation evaluation requires at least one recorded event")
    if any(
        not selection_fold.validation.contains(event.exchange_timestamp)
        for event in normalized
    ):
        raise ValueError("validation events must be confined to the validation window")

    candidate = ResearchCandidate.from_backtester(
        backtester,
        feature_ids=feature_ids,
    )
    result = backtester.run(list(normalized))
    provenance = ValidationProvenance(
        boundary_id=boundary_id,
        selection_fold_id=selection_fold.selection_fold_id,
        candidate_id=candidate.candidate_id,
        stream_digest=ReplayStream(events=normalized).stream_digest,
    )
    return ValidationBacktestResult(
        candidate=candidate,
        provenance=provenance,
        result=result,
    )


def score_validation_result(
    result: ValidationBacktestResult,
    *,
    objective: ValidationObjective,
) -> ValidationCandidateScore:
    if objective is ValidationObjective.TOTAL_RETURN:
        score = result.result.metrics.total_return
    else:
        score = result.result.metrics.max_drawdown_pct
    return ValidationCandidateScore(
        selection_fold_id=result.provenance.selection_fold_id,
        candidate_id=result.candidate.candidate_id,
        validation_result_id=result.result_id,
        objective_id=objective.value,
        direction=objective.direction,
        score=score,
    )


def _identity(prefix: str, payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(encoded).hexdigest()}"


def _decimal_identity(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == 0:
        return "0"
    return format(normalized, "f")


def _validate_digest(value: str, name: str) -> None:
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
