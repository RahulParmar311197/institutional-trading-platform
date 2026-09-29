import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum


class DataQuality(StrEnum):
    GOOD = "GOOD"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    INVALID = "INVALID"
    MISSING = "MISSING"


@dataclass(frozen=True, slots=True)
class Quote:
    instrument_id: uuid.UUID
    exchange_timestamp: datetime
    ingestion_timestamp: datetime
    bid: Decimal
    ask: Decimal
    bid_size: int | None = None
    ask_size: int | None = None
    source: str = "unknown"


@dataclass(frozen=True, slots=True)
class QualityAssessment:
    quality: DataQuality
    reasons: tuple[str, ...]

    @property
    def tradable(self) -> bool:
        return self.quality is DataQuality.GOOD


def assess_quote(
    quote: Quote,
    *,
    now: datetime,
    max_age: timedelta = timedelta(seconds=5),
) -> QualityAssessment:
    reasons: list[str] = []
    if quote.bid <= 0 or quote.ask <= 0:
        reasons.append("NON_POSITIVE_PRICE")
    if quote.bid > quote.ask:
        reasons.append("CROSSED_MARKET")
    if quote.exchange_timestamp > now + timedelta(seconds=1):
        reasons.append("FUTURE_TIMESTAMP")
    if now - quote.exchange_timestamp > max_age:
        reasons.append("STALE_QUOTE")

    invalid_reasons = {"NON_POSITIVE_PRICE", "CROSSED_MARKET", "FUTURE_TIMESTAMP"}
    if invalid_reasons.intersection(reasons):
        quality = DataQuality.INVALID
    elif "STALE_QUOTE" in reasons:
        quality = DataQuality.STALE
    else:
        quality = DataQuality.GOOD
    return QualityAssessment(quality=quality, reasons=tuple(reasons))
