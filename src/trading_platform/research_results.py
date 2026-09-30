import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal

from trading_platform.backtest import BacktestResult, ExecutionAssumptions
from trading_platform.research_periods import WalkForwardFold

OOS_RESULT_VERSION = 1


@dataclass(frozen=True, slots=True)
class OOSProvenance:
    boundary_id: str
    fold_id: str
    fold_spec_id: str
    strategy_id: str
    feature_ids: tuple[str, ...]
    stream_digest: str
    backtest_config_digest: str
    slippage_bps: Decimal
    fee_per_filled_order: Decimal
    version: int = OOS_RESULT_VERSION

    def __post_init__(self) -> None:
        if self.version != OOS_RESULT_VERSION:
            raise ValueError("unsupported OOS result version")
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
        _validate_digest(self.stream_digest, "stream_digest")
        _validate_digest(self.backtest_config_digest, "backtest_config_digest")
        if self.slippage_bps < 0:
            raise ValueError("slippage_bps must be non-negative")
        if self.fee_per_filled_order < 0:
            raise ValueError("fee_per_filled_order must be non-negative")

    @classmethod
    def from_fold(
        cls,
        *,
        boundary_id: str,
        fold: WalkForwardFold,
        strategy_id: str,
        feature_ids: tuple[str, ...],
        stream_digest: str,
        backtest_config_digest: str,
        assumptions: ExecutionAssumptions,
    ) -> "OOSProvenance":
        return cls(
            boundary_id=boundary_id,
            fold_id=fold.fold_id,
            fold_spec_id=fold.spec_id,
            strategy_id=strategy_id,
            feature_ids=feature_ids,
            stream_digest=stream_digest,
            backtest_config_digest=backtest_config_digest,
            slippage_bps=assumptions.slippage_bps,
            fee_per_filled_order=assumptions.fee_per_filled_order,
        )

    @property
    def provenance_id(self) -> str:
        payload = {
            "version": self.version,
            "boundary_id": self.boundary_id,
            "fold_id": self.fold_id,
            "fold_spec_id": self.fold_spec_id,
            "strategy_id": self.strategy_id,
            "feature_ids": self.feature_ids,
            "stream_digest": self.stream_digest,
            "backtest_config_digest": self.backtest_config_digest,
            "slippage_bps": _decimal_identity(self.slippage_bps),
            "fee_per_filled_order": _decimal_identity(self.fee_per_filled_order),
        }
        return f"oos_provenance_v{self.version}_{_sha256_json(payload)}"


@dataclass(frozen=True, slots=True)
class OOSBacktestResult:
    provenance: OOSProvenance
    result: BacktestResult

    @property
    def result_id(self) -> str:
        payload = {
            "provenance_id": self.provenance.provenance_id,
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
            "trades": [
                {
                    "event_id": trade.event_id,
                    "action": trade.action.value,
                    "quantity": trade.quantity,
                    "reference_price": _decimal_identity(trade.reference_price),
                    "fill_price": _decimal_identity(trade.fill_price),
                    "fee": _decimal_identity(trade.fee),
                    "realized_pnl_delta": _decimal_identity(trade.realized_pnl_delta),
                    "realized_pnl_after": _decimal_identity(trade.realized_pnl_after),
                }
                for trade in self.result.trades
            ],
            "equity_curve": [
                {
                    "event_id": point.event_id,
                    "mark_price": _decimal_identity(point.mark_price),
                    "equity": _decimal_identity(point.equity),
                    "drawdown": _decimal_identity(point.drawdown),
                    "drawdown_pct": _decimal_identity(point.drawdown_pct),
                }
                for point in self.result.equity_curve
            ],
        }
        return f"oos_result_v{self.provenance.version}_{_sha256_json(payload)}"


def _sha256_json(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _decimal_identity(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == 0:
        return "0"
    return format(normalized, "f")


def _validate_digest(value: str, name: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
