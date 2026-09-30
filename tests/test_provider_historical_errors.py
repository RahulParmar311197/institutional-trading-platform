from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
import pytest

from trading_platform.provider_historical import (
    DhanHistoricalClient,
    HistoricalBar,
    UpstoxHistoricalClient,
    UpstoxHistoricalUnit,
)

pytestmark = pytest.mark.asyncio


async def test_upstox_unsuccessful_payload_is_rejected() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "error", "data": {}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = UpstoxHistoricalClient(access_token="token", http_client=http)
        with pytest.raises(ValueError, match="unexpected Upstox"):
            await client.fetch(
                instrument_key="NSE_EQ|INE848E01016",
                unit=UpstoxHistoricalUnit.DAYS,
                interval=1,
                from_date=date(2025, 1, 1),
                to_date=date(2025, 1, 2),
            )


async def test_dhan_inconsistent_parallel_arrays_are_rejected() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "open": [100, 101],
                "high": [102],
                "low": [99, 100],
                "close": [101, 101],
                "volume": [10, 20],
                "timestamp": [1735689600, 1735776000],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = DhanHistoricalClient(access_token="token", http_client=http)
        with pytest.raises(ValueError, match="inconsistent lengths"):
            await client.fetch_daily(
                security_id="1333",
                exchange_segment="NSE_EQ",
                instrument="EQUITY",
                from_date=date(2025, 1, 1),
                to_date=date(2025, 1, 3),
            )


async def test_dhan_open_interest_length_mismatch_is_rejected() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "open": [100],
                "high": [102],
                "low": [99],
                "close": [101],
                "volume": [10],
                "timestamp": [1735689600],
                "open_interest": [1, 2],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = DhanHistoricalClient(access_token="token", http_client=http)
        with pytest.raises(ValueError, match="open_interest length"):
            await client.fetch_daily(
                security_id="1333",
                exchange_segment="NSE_EQ",
                instrument="EQUITY",
                from_date=date(2025, 1, 1),
                to_date=date(2025, 1, 2),
            )


async def test_dhan_intraday_rejects_timezone_aware_request_datetimes() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise AssertionError("HTTP must not be called for invalid request")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = DhanHistoricalClient(access_token="token", http_client=http)
        with pytest.raises(ValueError, match="provider-local naive"):
            await client.fetch_intraday(
                security_id="1333",
                exchange_segment="NSE_EQ",
                instrument="EQUITY",
                interval_minutes=5,
                from_datetime=datetime(2025, 1, 1, 9, 15, tzinfo=UTC),
                to_datetime=datetime(2025, 1, 1, 10, 15, tzinfo=UTC),
            )


def test_historical_bar_rejects_open_or_close_outside_range() -> None:
    with pytest.raises(ValueError, match="must not exceed high"):
        HistoricalBar(
            timestamp=datetime(2025, 1, 1, tzinfo=UTC),
            open=Decimal("103"),
            high=Decimal("102"),
            low=Decimal("99"),
            close=Decimal("101"),
            volume=1,
            open_interest=None,
            source="fixture",
        )

    with pytest.raises(ValueError, match="must not be below low"):
        HistoricalBar(
            timestamp=datetime(2025, 1, 1, tzinfo=UTC),
            open=Decimal("100"),
            high=Decimal("102"),
            low=Decimal("99"),
            close=Decimal("98"),
            volume=1,
            open_interest=None,
            source="fixture",
        )
