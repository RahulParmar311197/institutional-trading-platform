import json
import os
import uuid
from datetime import date
from decimal import Decimal

import httpx
import pytest

from trading_platform.config import Settings
from trading_platform.historical_service import (
    CanonicalDhanHistoricalService,
    CanonicalInstrumentNotFoundError,
    UnsupportedDhanInstrumentError,
)
from trading_platform.infrastructure import Infrastructure
from trading_platform.instruments import (
    Exchange,
    Instrument,
    InstrumentIdentifier,
    Segment,
)
from trading_platform.provider_historical import DhanHistoricalClient

pytestmark = pytest.mark.asyncio


def require_integration_tests() -> None:
    if os.environ.get("ITP_RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("set ITP_RUN_INTEGRATION_TESTS=1 to run PostgreSQL integration tests")


@pytest.mark.parametrize(
    ("exchange", "expected_exchange_segment"),
    [
        (Exchange.NSE, "NSE_EQ"),
        (Exchange.BSE, "BSE_EQ"),
    ],
)
async def test_canonical_dhan_daily_maps_cash_without_guessing(
    exchange: Exchange,
    expected_exchange_segment: str,
) -> None:
    require_integration_tests()
    infrastructure = Infrastructure(Settings(_env_file=None))
    instrument_id = uuid.uuid4()
    security_id = str(900000 + (instrument_id.int % 99999))
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "open": [100],
                "high": [102],
                "low": [99],
                "close": [101],
                "volume": [10],
                "timestamp": [1754006400],
            },
        )

    try:
        async with infrastructure.sessions() as session:
            session.add(
                Instrument(
                    id=instrument_id,
                    exchange=exchange,
                    segment=Segment.CASH,
                    trading_symbol=f"DHAN-{exchange.value}-{instrument_id.hex[:8]}",
                    name=f"Canonical Dhan {exchange.value} Cash Test",
                    lot_size=1,
                    tick_size=Decimal("0.05"),
                    active=True,
                )
            )
            session.add(
                InstrumentIdentifier(
                    instrument_id=instrument_id,
                    provider="dhan",
                    external_id=security_id,
                    valid_from=date(2025, 8, 1),
                    valid_to=date(2025, 8, 1),
                )
            )
            await session.commit()

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            service = CanonicalDhanHistoricalService(
                sessions=infrastructure.sessions,
                client=DhanHistoricalClient(access_token="token", http_client=http),
            )
            bars = await service.fetch_daily(
                instrument_id=instrument_id,
                from_date=date(2025, 8, 1),
                to_date=date(2025, 8, 2),
            )

        assert len(bars) == 1
        assert bars[0].close == Decimal("101")
        assert requests == [
            {
                "securityId": security_id,
                "exchangeSegment": expected_exchange_segment,
                "instrument": "EQUITY",
                "expiryCode": 0,
                "oi": False,
                "fromDate": "2025-08-01",
                "toDate": "2025-08-02",
            }
        ]
    finally:
        await infrastructure.close()


async def test_canonical_dhan_daily_rejects_derivative_before_http() -> None:
    require_integration_tests()
    infrastructure = Infrastructure(Settings(_env_file=None))
    instrument_id = uuid.uuid4()
    http_called = False

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal http_called
        http_called = True
        return httpx.Response(500)

    try:
        async with infrastructure.sessions() as session:
            session.add(
                Instrument(
                    id=instrument_id,
                    exchange=Exchange.NSE,
                    segment=Segment.FUTURES,
                    trading_symbol=f"DHAN-FUT-{instrument_id.hex[:8]}",
                    name="Canonical Dhan Futures Safety Test",
                    expiry=date(2025, 8, 28),
                    lot_size=25,
                    tick_size=Decimal("0.05"),
                    active=True,
                )
            )
            session.add(
                InstrumentIdentifier(
                    instrument_id=instrument_id,
                    provider="dhan",
                    external_id=str(800000 + (instrument_id.int % 99999)),
                    valid_from=date(2025, 8, 1),
                    valid_to=date(2025, 8, 28),
                )
            )
            await session.commit()

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            service = CanonicalDhanHistoricalService(
                sessions=infrastructure.sessions,
                client=DhanHistoricalClient(access_token="token", http_client=http),
            )
            with pytest.raises(UnsupportedDhanInstrumentError, match="cash equities only"):
                await service.fetch_daily(
                    instrument_id=instrument_id,
                    from_date=date(2025, 8, 1),
                    to_date=date(2025, 8, 2),
                )

        assert http_called is False
    finally:
        await infrastructure.close()


async def test_canonical_dhan_daily_rejects_missing_canonical_instrument_before_http() -> None:
    require_integration_tests()
    infrastructure = Infrastructure(Settings(_env_file=None))
    instrument_id = uuid.uuid4()
    http_called = False

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal http_called
        http_called = True
        return httpx.Response(500)

    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            service = CanonicalDhanHistoricalService(
                sessions=infrastructure.sessions,
                client=DhanHistoricalClient(access_token="token", http_client=http),
            )
            with pytest.raises(CanonicalInstrumentNotFoundError):
                await service.fetch_daily(
                    instrument_id=instrument_id,
                    from_date=date(2025, 8, 1),
                    to_date=date(2025, 8, 2),
                )

        assert http_called is False
    finally:
        await infrastructure.close()


async def test_canonical_dhan_daily_validates_range_before_database_or_http() -> None:
    require_integration_tests()
    infrastructure = Infrastructure(Settings(_env_file=None))
    http_called = False

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal http_called
        http_called = True
        return httpx.Response(500)

    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            service = CanonicalDhanHistoricalService(
                sessions=infrastructure.sessions,
                client=DhanHistoricalClient(access_token="token", http_client=http),
            )
            with pytest.raises(ValueError, match="non-inclusive"):
                await service.fetch_daily(
                    instrument_id=uuid.uuid4(),
                    from_date=date(2025, 8, 2),
                    to_date=date(2025, 8, 2),
                )

        assert http_called is False
    finally:
        await infrastructure.close()
