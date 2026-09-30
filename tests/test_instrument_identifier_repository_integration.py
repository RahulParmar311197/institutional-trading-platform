import os
import uuid
from datetime import date
from decimal import Decimal

import pytest

from trading_platform.config import Settings
from trading_platform.infrastructure import Infrastructure
from trading_platform.instrument_identifiers import (
    AmbiguousInstrumentIdentifierError,
    InstrumentIdentifierNotFoundError,
    InstrumentIdentifierRepository,
)
from trading_platform.instruments import (
    Exchange,
    Instrument,
    InstrumentIdentifier,
    Segment,
)

pytestmark = pytest.mark.asyncio


async def test_provider_identifier_resolution_respects_validity_windows() -> None:
    if os.environ.get("ITP_RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("set ITP_RUN_INTEGRATION_TESTS=1 to run PostgreSQL integration tests")

    infrastructure = Infrastructure(Settings(_env_file=None))
    instrument_id = uuid.uuid4()
    try:
        async with infrastructure.sessions() as session:
            session.add(
                Instrument(
                    id=instrument_id,
                    exchange=Exchange.NSE,
                    segment=Segment.CASH,
                    trading_symbol=f"IDENT-{instrument_id.hex[:8]}",
                    name="Identifier Resolution Test",
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
                        external_id=f"NSE_EQ|OLD-{instrument_id.hex[:8]}",
                        valid_from=date(2025, 1, 1),
                        valid_to=date(2025, 6, 30),
                    ),
                    InstrumentIdentifier(
                        instrument_id=instrument_id,
                        provider="upstox",
                        external_id=f"NSE_EQ|NEW-{instrument_id.hex[:8]}",
                        valid_from=date(2025, 7, 1),
                        valid_to=None,
                    ),
                ]
            )
            await session.commit()

        async with infrastructure.sessions() as session:
            repository = InstrumentIdentifierRepository(session)
            old = await repository.resolve(
                instrument_id=instrument_id,
                provider="upstox",
                on_date=date(2025, 3, 1),
            )
            new = await repository.resolve(
                instrument_id=instrument_id,
                provider="upstox",
                on_date=date(2025, 9, 1),
            )

            assert old.startswith("NSE_EQ|OLD-")
            assert new.startswith("NSE_EQ|NEW-")

            with pytest.raises(InstrumentIdentifierNotFoundError):
                await repository.resolve(
                    instrument_id=instrument_id,
                    provider="dhan",
                    on_date=date(2025, 9, 1),
                )
            with pytest.raises(ValueError, match="provider must not be empty"):
                await repository.resolve(
                    instrument_id=instrument_id,
                    provider=" ",
                    on_date=date(2025, 9, 1),
                )
    finally:
        await infrastructure.close()


async def test_overlapping_provider_identifier_windows_fail_closed() -> None:
    if os.environ.get("ITP_RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("set ITP_RUN_INTEGRATION_TESTS=1 to run PostgreSQL integration tests")

    infrastructure = Infrastructure(Settings(_env_file=None))
    instrument_id = uuid.uuid4()
    try:
        async with infrastructure.sessions() as session:
            session.add(
                Instrument(
                    id=instrument_id,
                    exchange=Exchange.NSE,
                    segment=Segment.CASH,
                    trading_symbol=f"AMBIG-{instrument_id.hex[:8]}",
                    name="Ambiguous Identifier Test",
                    lot_size=1,
                    tick_size=Decimal("0.05"),
                    active=True,
                )
            )
            session.add_all(
                [
                    InstrumentIdentifier(
                        instrument_id=instrument_id,
                        provider="dhan",
                        external_id=f"FIRST-{instrument_id.hex[:8]}",
                        valid_from=date(2025, 1, 1),
                        valid_to=None,
                    ),
                    InstrumentIdentifier(
                        instrument_id=instrument_id,
                        provider="dhan",
                        external_id=f"SECOND-{instrument_id.hex[:8]}",
                        valid_from=date(2025, 6, 1),
                        valid_to=None,
                    ),
                ]
            )
            await session.commit()

        async with infrastructure.sessions() as session:
            with pytest.raises(AmbiguousInstrumentIdentifierError):
                await InstrumentIdentifierRepository(session).resolve(
                    instrument_id=instrument_id,
                    provider="dhan",
                    on_date=date(2025, 9, 1),
                )
    finally:
        await infrastructure.close()
