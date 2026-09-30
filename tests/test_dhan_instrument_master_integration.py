import os
import uuid
from decimal import Decimal

import pytest

from trading_platform.config import Settings
from trading_platform.dhan_instrument_master import (
    DhanInstrumentMasterConflictError,
    DhanInstrumentMasterRecord,
    DhanInstrumentMasterSynchronizer,
)
from trading_platform.infrastructure import Infrastructure
from trading_platform.instruments import (
    Exchange,
    Instrument,
    InstrumentIdentifier,
    Segment,
)

pytestmark = pytest.mark.asyncio


def require_integration_tests() -> None:
    if os.environ.get("ITP_RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("set ITP_RUN_INTEGRATION_TESTS=1 to run PostgreSQL integration tests")


async def test_dhan_master_sync_populates_existing_identifier_metadata_only() -> None:
    require_integration_tests()
    infrastructure = Infrastructure(Settings(_env_file=None))
    matched_id = uuid.uuid4()
    unmatched_id = uuid.uuid4()
    matched_security_id = str(500000 + (matched_id.int % 99999))
    unmatched_security_id = str(600000 + (unmatched_id.int % 99999))

    try:
        async with infrastructure.sessions() as session:
            session.add_all(
                [
                    Instrument(
                        id=matched_id,
                        exchange=Exchange.NSE,
                        segment=Segment.FUTURES,
                        trading_symbol=f"MASTER-{matched_id.hex[:8]}",
                        name="Dhan Master Matched Test",
                        lot_size=25,
                        tick_size=Decimal("0.05"),
                        active=True,
                    ),
                    Instrument(
                        id=unmatched_id,
                        exchange=Exchange.NSE,
                        segment=Segment.CASH,
                        trading_symbol=f"MASTER-{unmatched_id.hex[:8]}",
                        name="Dhan Master Unmatched Test",
                        lot_size=1,
                        tick_size=Decimal("0.05"),
                        active=True,
                    ),
                ]
            )
            session.add_all(
                [
                    InstrumentIdentifier(
                        instrument_id=matched_id,
                        provider="dhan",
                        external_id=matched_security_id,
                    ),
                    InstrumentIdentifier(
                        instrument_id=unmatched_id,
                        provider="dhan",
                        external_id=unmatched_security_id,
                    ),
                ]
            )
            await session.commit()

        records = (
            DhanInstrumentMasterRecord(
                security_id=matched_security_id,
                exchange_segment="NSE_FNO",
                instrument_type="FUTSTK",
                expiry_code=1,
            ),
            DhanInstrumentMasterRecord(
                security_id="provider-only-id",
                exchange_segment="NSE_EQ",
                instrument_type="EQUITY",
                expiry_code=None,
            ),
        )
        async with infrastructure.sessions() as session:
            result = await DhanInstrumentMasterSynchronizer(session).synchronize(records)
            await session.commit()

            assert result.matched == 1
            assert result.updated == 1
            assert result.unchanged == 0
            assert result.unmatched_identifiers == 1

        async with infrastructure.sessions() as session:
            matched = await session.scalar(
                InstrumentIdentifier.__table__.select().where(
                    InstrumentIdentifier.instrument_id == matched_id
                )
            )
            # SQLAlchemy Core scalar returns the first selected column, so use ORM get below.
            assert matched is not None
            matched_identifier = await session.scalar(
                __import__("sqlalchemy").select(InstrumentIdentifier).where(
                    InstrumentIdentifier.instrument_id == matched_id
                )
            )
            unmatched_identifier = await session.scalar(
                __import__("sqlalchemy").select(InstrumentIdentifier).where(
                    InstrumentIdentifier.instrument_id == unmatched_id
                )
            )
            assert matched_identifier is not None
            assert matched_identifier.provider_exchange_segment == "NSE_FNO"
            assert matched_identifier.provider_instrument_type == "FUTSTK"
            assert matched_identifier.provider_expiry_code == 1
            assert unmatched_identifier is not None
            assert unmatched_identifier.provider_exchange_segment is None
            assert unmatched_identifier.provider_instrument_type is None
            assert unmatched_identifier.provider_expiry_code is None
    finally:
        await infrastructure.close()


async def test_dhan_master_sync_detects_all_conflicts_before_mutation() -> None:
    require_integration_tests()
    infrastructure = Infrastructure(Settings(_env_file=None))
    first_id = uuid.uuid4()
    conflict_id = uuid.uuid4()
    first_security_id = str(700000 + (first_id.int % 99999))
    conflict_security_id = str(800000 + (conflict_id.int % 99999))

    try:
        async with infrastructure.sessions() as session:
            session.add_all(
                [
                    Instrument(
                        id=first_id,
                        exchange=Exchange.NSE,
                        segment=Segment.FUTURES,
                        trading_symbol=f"SYNC-{first_id.hex[:8]}",
                        name="Dhan Sync First Test",
                        lot_size=25,
                        tick_size=Decimal("0.05"),
                        active=True,
                    ),
                    Instrument(
                        id=conflict_id,
                        exchange=Exchange.NSE,
                        segment=Segment.FUTURES,
                        trading_symbol=f"SYNC-{conflict_id.hex[:8]}",
                        name="Dhan Sync Conflict Test",
                        lot_size=25,
                        tick_size=Decimal("0.05"),
                        active=True,
                    ),
                ]
            )
            session.add_all(
                [
                    InstrumentIdentifier(
                        instrument_id=first_id,
                        provider="dhan",
                        external_id=first_security_id,
                    ),
                    InstrumentIdentifier(
                        instrument_id=conflict_id,
                        provider="dhan",
                        external_id=conflict_security_id,
                        provider_exchange_segment="BSE_FNO",
                        provider_instrument_type="FUTSTK",
                        provider_expiry_code=0,
                    ),
                ]
            )
            await session.commit()

        records = (
            DhanInstrumentMasterRecord(
                security_id=first_security_id,
                exchange_segment="NSE_FNO",
                instrument_type="FUTSTK",
                expiry_code=0,
            ),
            DhanInstrumentMasterRecord(
                security_id=conflict_security_id,
                exchange_segment="NSE_FNO",
                instrument_type="FUTSTK",
                expiry_code=0,
            ),
        )
        async with infrastructure.sessions() as session:
            with pytest.raises(
                DhanInstrumentMasterConflictError,
                match="provider_exchange_segment",
            ):
                await DhanInstrumentMasterSynchronizer(session).synchronize(records)

            first_identifier = await session.scalar(
                __import__("sqlalchemy").select(InstrumentIdentifier).where(
                    InstrumentIdentifier.instrument_id == first_id
                )
            )
            assert first_identifier is not None
            assert first_identifier.provider_exchange_segment is None
            assert first_identifier.provider_instrument_type is None
            assert first_identifier.provider_expiry_code is None
    finally:
        await infrastructure.close()
