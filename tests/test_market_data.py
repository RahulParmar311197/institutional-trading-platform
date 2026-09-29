import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from trading_platform.market_data import DataQuality, Quote, assess_quote


def quote_at(now: datetime, *, bid: str = "100", ask: str = "101", age_seconds: int = 0) -> Quote:
    return Quote(
        instrument_id=uuid.uuid4(),
        exchange_timestamp=now - timedelta(seconds=age_seconds),
        ingestion_timestamp=now,
        bid=Decimal(bid),
        ask=Decimal(ask),
        source="test",
    )


def test_good_quote_is_tradable() -> None:
    now = datetime.now(UTC)
    result = assess_quote(quote_at(now), now=now)
    assert result.quality is DataQuality.GOOD
    assert result.tradable is True


def test_stale_quote_is_not_tradable() -> None:
    now = datetime.now(UTC)
    result = assess_quote(quote_at(now, age_seconds=10), now=now)
    assert result.quality is DataQuality.STALE
    assert result.tradable is False
    assert "STALE_QUOTE" in result.reasons


def test_crossed_market_is_invalid() -> None:
    now = datetime.now(UTC)
    result = assess_quote(quote_at(now, bid="102", ask="101"), now=now)
    assert result.quality is DataQuality.INVALID
    assert result.tradable is False
    assert "CROSSED_MARKET" in result.reasons
