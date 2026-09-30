import hashlib
import json
import random
from dataclasses import dataclass
from decimal import Decimal

from trading_platform.research_returns import PeriodicReturn, ReturnPeriodSpec

MONTE_CARLO_SPEC_VERSION = 1


@dataclass(frozen=True, slots=True)
class MovingBlockBootstrapSpec:
    block_length: int
    path_count: int
    seed: int
    version: int = MONTE_CARLO_SPEC_VERSION

    def __post_init__(self) -> None:
        if self.version != MONTE_CARLO_SPEC_VERSION:
            raise ValueError("unsupported Monte Carlo specification version")
        if type(self.block_length) is not int or self.block_length <= 0:
            raise ValueError("block_length must be a positive integer")
        if type(self.path_count) is not int or self.path_count <= 0:
            raise ValueError("path_count must be a positive integer")
        if type(self.seed) is not int:
            raise ValueError("seed must be an integer")

    @property
    def spec_id(self) -> str:
        payload = {
            "version": self.version,
            "block_length": self.block_length,
            "path_count": self.path_count,
            "seed": self.seed,
        }
        return _identity(f"moving_block_bootstrap_v{self.version}", payload)


@dataclass(frozen=True, slots=True)
class BootstrapPath:
    index: int
    simple_returns: tuple[Decimal, ...]

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("bootstrap path index must be non-negative")
        if not self.simple_returns:
            raise ValueError("bootstrap path requires returns")

    @property
    def cumulative_return(self) -> Decimal:
        growth = Decimal("1")
        for value in self.simple_returns:
            growth *= Decimal("1") + value
        return growth - Decimal("1")


@dataclass(frozen=True, slots=True)
class MovingBlockBootstrapResult:
    spec_id: str
    return_period_spec_id: str
    source_digest: str
    paths: tuple[BootstrapPath, ...]

    def __post_init__(self) -> None:
        if not self.spec_id.strip():
            raise ValueError("spec_id must not be empty")
        if not self.return_period_spec_id.strip():
            raise ValueError("return_period_spec_id must not be empty")
        _validate_digest(self.source_digest, "source_digest")
        if not self.paths:
            raise ValueError("Monte Carlo result requires paths")
        if tuple(path.index for path in self.paths) != tuple(range(len(self.paths))):
            raise ValueError("Monte Carlo paths must be ordered and contiguous from index 0")
        lengths = {len(path.simple_returns) for path in self.paths}
        if len(lengths) != 1:
            raise ValueError("Monte Carlo paths must have equal lengths")

    @property
    def result_id(self) -> str:
        payload = {
            "spec_id": self.spec_id,
            "return_period_spec_id": self.return_period_spec_id,
            "source_digest": self.source_digest,
            "paths": [
                {
                    "index": path.index,
                    "returns": [_decimal_identity(value) for value in path.simple_returns],
                }
                for path in self.paths
            ],
        }
        return _identity("moving_block_bootstrap_result_v1", payload)


def moving_block_bootstrap(
    returns: tuple[PeriodicReturn, ...],
    *,
    return_period_spec: ReturnPeriodSpec,
    spec: MovingBlockBootstrapSpec,
) -> MovingBlockBootstrapResult:
    _validate_return_series(returns, return_period_spec=return_period_spec)
    if spec.block_length > len(returns):
        raise ValueError("block_length must not exceed source return count")

    source_values = tuple(item.simple_return for item in returns)
    source_digest = _source_digest(returns, return_period_spec=return_period_spec)
    rng = random.Random(spec.seed)  # nosec B311 - deterministic research resampling, not crypto
    max_start = len(source_values) - spec.block_length
    paths: list[BootstrapPath] = []
    for path_index in range(spec.path_count):
        sampled: list[Decimal] = []
        while len(sampled) < len(source_values):
            start = rng.randint(0, max_start)  # nosec B311
            sampled.extend(source_values[start : start + spec.block_length])
        paths.append(
            BootstrapPath(
                index=path_index,
                simple_returns=tuple(sampled[: len(source_values)]),
            )
        )

    return MovingBlockBootstrapResult(
        spec_id=spec.spec_id,
        return_period_spec_id=return_period_spec.spec_id,
        source_digest=source_digest,
        paths=tuple(paths),
    )


def _validate_return_series(
    returns: tuple[PeriodicReturn, ...],
    *,
    return_period_spec: ReturnPeriodSpec,
) -> None:
    if not returns:
        raise ValueError("moving-block bootstrap requires source returns")
    previous_end = None
    for item in returns:
        if item.period_end - item.period_start != return_period_spec.period:
            raise ValueError("source returns must match the explicit return period")
        if previous_end is not None and item.period_start != previous_end:
            raise ValueError("source returns must be contiguous")
        if item.simple_return <= Decimal("-1"):
            raise ValueError("simple returns must be greater than -1")
        previous_end = item.period_end


def _source_digest(
    returns: tuple[PeriodicReturn, ...],
    *,
    return_period_spec: ReturnPeriodSpec,
) -> str:
    payload = {
        "return_period_spec_id": return_period_spec.spec_id,
        "returns": [
            {
                "period_start": item.period_start.isoformat(),
                "period_end": item.period_end.isoformat(),
                "simple_return": _decimal_identity(item.simple_return),
            }
            for item in returns
        ],
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
