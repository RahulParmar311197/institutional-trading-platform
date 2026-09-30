import os
import uuid
from datetime import date
from decimal import Decimal

import httpx
import pytest

from trading_platform.config import Settings
from trading_platform.historical_service import CanonicalUpstoxHistoricalService
from trading_platform.infrastructure import Infrastructure
from trading_platform.instrument_identifiers import InstrumentIdentifierRangeNotCoveredError
from trading_platform.instruments import (
    Exchange,
    Instrument,
    InstrumentIdentifier,
    Segment,
)
from trading_platform.provider_historical import UpstoxHistoricalClient, UpstoxHistoricalUnit

pytestmark = pytest.mark.asyncio


async def test_canonical_upstox_service_resolves_provider_id_before_read() -> None:
    if os.environ.get("ITP_RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("set ITP_RUN_INTEGRATION_TESTS=1 to run PostgreSQL integration tests")

    infrastructure = Infrastructure(Settings(_env_file=None))
    instrument_id = uuid.uuid4()
    external_id = f"NSE_EQ|SERVICE-{instrument_id.hex[:8]}"
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "candles": [
                        [
                            "2025-08-01T09:15:00+05:30",
                            100,
                            102,
                            99,
                            101,
                            10,
                            5,
                        ]
                    ]
                },
            },
        )

    try:
        async with infrastructure.sessions() as session:
            session.add(
                Instrument(
                    id=instrument_id,
                    exchange=Exchange.NSE,
                    segment=Segment.CASH,
                    trading_symbol=f"SERVICE-{instrument_id.hex[:8]}",
                    name="Canonical Upstox Service Test",
                    lot_size=1,
                    tick_size=Decimal("0.05"),
                    active=True,
                )
            )
            session.add(
                InstrumentIdentifier(
                    instrument_id=instrument_id,
                    provider="upstox",
                    external_id=external_id,
                    valid_from=date(2025, 7, 1),
                    valid_to=None,
                )
            )
            await session.commit()

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            service = CanonicalUpstoxHistoricalService(
                sessions=infrastructure.sessions,
                client=UpstoxHistoricalClient(access_token="token", http_client=http),
            )
            bars = await service.fetch(
                instrument_id=instrument_id,
                unit=UpstoxHistoricalUnit.DAYS,
                interval=1,
                from_date=date(2025, 8, 1),
                to_date=date(2025, 8, 2),
            )

        assert len(bars) == 1
        assert bars[0].close == Decimal("101")
        assert len(seen_urls) == 1
        assert "NSE_EQ%7CSERVICE-" in seen_urls[0]
    finally:
        await infrastructure.close()


async def test_canonical_upstox_service_rejects_identifier_rollover_before_http() -> None:
    if os.environ.get("ITP_RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("set ITP_RUN_INTEGRATION_TESTS=1 to run PostgreSQL integration tests")

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
                    segment=Segment.CASH,
                    trading_symbol=f"ROLLOVER-{instrument_id.hex[:8]}",
                    name="Upstox Rollover Test",
                    lot_size=1,
                    tick_size=Decimal("0.05"),
                    active=True,
                )
            )
            session.add_all(
                [
                    InstrumentIdentifier(
                        instrument_id=instrument_id,
                        provider="upstox",
                        external_id=f"NSE_EQ|OLD-SERVICE-{instrument_id.hex[:8]}",
                        valid_from=date(2025, 1, 1),
                        valid_to=date(2025, 6, 30),
                    ),
                    InstrumentIdentifier(
                        instrument_id=instrument_id,
                        provider="upstox",
                        external_id=f"NSE_EQ|NEW-SERVICE-{instrument_id.hex[:8]}",
                        valid_from=date(2025, 7, 1),
                        valid_to=None,
                    ),
                ]
            )
            await session.commit()

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            service = CanonicalUpstoxHistoricalService(
                sessions=infrastructure.sessions,
                client=UpstoxHistoricalClient(access_token="token", http_client=http),
            )
            with pytest.raises(InstrumentIdentifierRangeNotCoveredError):
                await service.fetch(
                    instrument_id=instrument_id,
                    unit=UpstoxHistoricalUnit.DAYS,
                    interval=1,
                    from_date=date(2025, 6, 1),
                    to_date=date(2025, 8, 1),
                )

        assert http_called is False
    finally:
        await infrastructure.close()
