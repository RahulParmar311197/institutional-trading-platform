import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
import pytest

from trading_platform.provider_historical import (
    DhanHistoricalClient,
    HistoricalRetryPolicy,
    UpstoxHistoricalClient,
    UpstoxHistoricalUnit,
)

pytestmark = pytest.mark.asyncio


async def test_upstox_v3_historical_request_and_response_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == (
            "https://api.upstox.com/v3/historical-candle/"
            "NSE_EQ%7CINE848E01016/minutes/1/2025-01-02/2025-01-01"
        )
        assert request.headers["Authorization"] == "Bearer test-token"
        assert request.headers["Accept"] == "application/json"
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "candles": [
                        [
                            "2025-01-01T09:16:00+05:30",
                            101,
                            103,
                            100,
                            102,
                            20,
                            7,
                        ],
                        [
                            "2025-01-01T09:15:00+05:30",
                            100,
                            102,
                            99,
                            101,
                            10,
                            5,
                        ],
                    ]
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        bars = await UpstoxHistoricalClient(
            access_token="test-token",
            http_client=http,
        ).fetch(
            instrument_key="NSE_EQ|INE848E01016",
            unit=UpstoxHistoricalUnit.MINUTES,
            interval=1,
            from_date=date(2025, 1, 1),
            to_date=date(2025, 1, 2),
        )

    assert len(bars) == 2
    assert bars[0].timestamp.isoformat() == "2025-01-01T09:15:00+05:30"
    assert bars[0].open == Decimal("100")
    assert bars[0].close == Decimal("101")
    assert bars[0].volume == 10
    assert bars[0].open_interest == 5
    assert bars[0].source == "upstox_v3_historical"


async def test_upstox_interval_validation_happens_before_http() -> None:
    called = False

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = UpstoxHistoricalClient(access_token="test-token", http_client=http)
        with pytest.raises(ValueError, match="invalid interval"):
            await client.fetch(
                instrument_key="NSE_EQ|INE848E01016",
                unit=UpstoxHistoricalUnit.DAYS,
                interval=2,
                from_date=date(2025, 1, 1),
                to_date=date(2025, 1, 2),
            )

    assert called is False


async def test_dhan_daily_request_and_parallel_array_response_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "https://api.dhan.co/v2/charts/historical"
        assert request.headers["access-token"] == "dhan-token"
        payload = json.loads(request.content)
        assert payload == {
            "securityId": "1333",
            "exchangeSegment": "NSE_EQ",
            "instrument": "EQUITY",
            "expiryCode": 0,
            "oi": True,
            "fromDate": "2025-01-01",
            "toDate": "2025-01-03",
        }
        return httpx.Response(
            200,
            json={
                "open": [100, 101],
                "high": [103, 104],
                "low": [99, 100],
                "close": [102, 103],
                "volume": [1000, 2000],
                "timestamp": [1735689600, 1735776000],
                "open_interest": [10, 20],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        bars = await DhanHistoricalClient(
            access_token="dhan-token",
            http_client=http,
        ).fetch_daily(
            security_id="1333",
            exchange_segment="NSE_EQ",
            instrument="EQUITY",
            from_date=date(2025, 1, 1),
            to_date=date(2025, 1, 3),
            include_open_interest=True,
        )

    assert len(bars) == 2
    assert bars[0].timestamp == datetime(2025, 1, 1, tzinfo=UTC)
    assert bars[1].close == Decimal("103")
    assert bars[1].open_interest == 20
    assert bars[1].source == "dhan_v2_daily"


async def test_dhan_intraday_request_and_90_day_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert str(request.url) == "https://api.dhan.co/v2/charts/intraday"
        assert payload["interval"] == "5"
        assert payload["fromDate"] == "2025-01-01 09:15:00"
        assert payload["toDate"] == "2025-01-02 15:30:00"
        return httpx.Response(
            200,
            json={
                "open": [100],
                "high": [101],
                "low": [99],
                "close": [100.5],
                "volume": [50],
                "timestamp": [1735703100],
                "open_interest": [0],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = DhanHistoricalClient(access_token="dhan-token", http_client=http)
        bars = await client.fetch_intraday(
            security_id="1333",
            exchange_segment="NSE_EQ",
            instrument="EQUITY",
            interval_minutes=5,
            from_datetime=datetime(2025, 1, 1, 9, 15),
            to_datetime=datetime(2025, 1, 2, 15, 30),
        )
        assert len(bars) == 1
        assert bars[0].close == Decimal("100.5")
        assert bars[0].source == "dhan_v2_intraday"

        with pytest.raises(ValueError, match="90 days"):
            await client.fetch_intraday(
                security_id="1333",
                exchange_segment="NSE_EQ",
                instrument="EQUITY",
                interval_minutes=5,
                from_datetime=datetime(2025, 1, 1, 9, 15),
                to_datetime=datetime(2025, 1, 1, 9, 15) + timedelta(days=91),
            )


async def test_historical_read_retries_transient_status_then_succeeds() -> None:
    attempts = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(503, json={"error": "temporarily unavailable"})
        return httpx.Response(
            200,
            json={"status": "success", "data": {"candles": []}},
        )

    policy = HistoricalRetryPolicy(
        max_attempts=3,
        base_delay_seconds=0,
        max_delay_seconds=0,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        bars = await UpstoxHistoricalClient(
            access_token="test-token",
            http_client=http,
            retry_policy=policy,
        ).fetch(
            instrument_key="NSE_EQ|INE848E01016",
            unit=UpstoxHistoricalUnit.DAYS,
            interval=1,
            from_date=date(2025, 1, 1),
            to_date=date(2025, 1, 2),
        )

    assert attempts == 3
    assert bars == ()


async def test_historical_read_does_not_retry_auth_failure() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(401, request=request, json={"error": "unauthorized"})

    policy = HistoricalRetryPolicy(
        max_attempts=3,
        base_delay_seconds=0,
        max_delay_seconds=0,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = DhanHistoricalClient(
            access_token="bad-token",
            http_client=http,
            retry_policy=policy,
        )
        with pytest.raises(httpx.HTTPStatusError):
            await client.fetch_daily(
                security_id="1333",
                exchange_segment="NSE_EQ",
                instrument="EQUITY",
                from_date=date(2025, 1, 1),
                to_date=date(2025, 1, 2),
            )

    assert attempts == 1


async def test_historical_read_retries_transport_error_then_raises() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("simulated connection loss", request=request)

    policy = HistoricalRetryPolicy(
        max_attempts=2,
        base_delay_seconds=0,
        max_delay_seconds=0,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = UpstoxHistoricalClient(
            access_token="test-token",
            http_client=http,
            retry_policy=policy,
        )
        with pytest.raises(httpx.ConnectError, match="simulated connection loss"):
            await client.fetch(
                instrument_key="NSE_EQ|INE848E01016",
                unit=UpstoxHistoricalUnit.DAYS,
                interval=1,
                from_date=date(2025, 1, 1),
                to_date=date(2025, 1, 2),
            )

    assert attempts == 2


def test_historical_retry_policy_rejects_unsafe_configuration() -> None:
    with pytest.raises(ValueError, match="positive"):
        HistoricalRetryPolicy(max_attempts=0)
    with pytest.raises(ValueError, match="must not exceed 10"):
        HistoricalRetryPolicy(max_attempts=11)
    with pytest.raises(ValueError, match="max_delay_seconds"):
        HistoricalRetryPolicy(base_delay_seconds=1, max_delay_seconds=0.5)
    with pytest.raises(ValueError, match="transient HTTP statuses only"):
        HistoricalRetryPolicy(retry_status_codes=frozenset({401}))


async def test_provider_clients_reject_empty_tokens() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(ValueError, match="access_token"):
            UpstoxHistoricalClient(access_token=" ", http_client=http)
        with pytest.raises(ValueError, match="access_token"):
            DhanHistoricalClient(access_token=" ", http_client=http)
