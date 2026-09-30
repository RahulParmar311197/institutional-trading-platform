import uuid
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from trading_platform.instrument_identifiers import InstrumentIdentifierRepository
from trading_platform.instruments import Exchange, Instrument, Segment
from trading_platform.provider_historical import (
    DhanHistoricalClient,
    HistoricalBar,
    UpstoxHistoricalClient,
    UpstoxHistoricalUnit,
)

UPSTOX_PROVIDER = "upstox"
DHAN_PROVIDER = "dhan"


class CanonicalInstrumentNotFoundError(LookupError):
    pass


class UnsupportedDhanInstrumentError(ValueError):
    pass


class CanonicalUpstoxHistoricalService:
    def __init__(
        self,
        *,
        sessions: async_sessionmaker[AsyncSession],
        client: UpstoxHistoricalClient,
    ) -> None:
        self.sessions = sessions
        self.client = client

    async def fetch(
        self,
        *,
        instrument_id: uuid.UUID,
        unit: UpstoxHistoricalUnit,
        interval: int,
        from_date: date,
        to_date: date,
    ) -> tuple[HistoricalBar, ...]:
        async with self.sessions() as session:
            instrument_key = await InstrumentIdentifierRepository(session).resolve_range(
                instrument_id=instrument_id,
                provider=UPSTOX_PROVIDER,
                start_date=from_date,
                end_date=to_date,
            )

        return await self.client.fetch(
            instrument_key=instrument_key,
            unit=unit,
            interval=interval,
            from_date=from_date,
            to_date=to_date,
        )


class CanonicalDhanHistoricalService:
    def __init__(
        self,
        *,
        sessions: async_sessionmaker[AsyncSession],
        client: DhanHistoricalClient,
    ) -> None:
        self.sessions = sessions
        self.client = client

    async def fetch_daily(
        self,
        *,
        instrument_id: uuid.UUID,
        from_date: date,
        to_date: date,
    ) -> tuple[HistoricalBar, ...]:
        if from_date >= to_date:
            raise ValueError("Dhan daily to_date is non-inclusive and must follow from_date")

        coverage_end = to_date - timedelta(days=1)
        async with self.sessions() as session:
            instrument = await session.get(Instrument, instrument_id)
            if instrument is None:
                raise CanonicalInstrumentNotFoundError(
                    f"canonical instrument {instrument_id} does not exist"
                )
            exchange_segment, instrument_type = _dhan_cash_classification(instrument)
            security_id = await InstrumentIdentifierRepository(session).resolve_range(
                instrument_id=instrument_id,
                provider=DHAN_PROVIDER,
                start_date=from_date,
                end_date=coverage_end,
            )

        return await self.client.fetch_daily(
            security_id=security_id,
            exchange_segment=exchange_segment,
            instrument=instrument_type,
            from_date=from_date,
            to_date=to_date,
        )


def _dhan_cash_classification(instrument: Instrument) -> tuple[str, str]:
    if instrument.segment is not Segment.CASH:
        raise UnsupportedDhanInstrumentError(
            "canonical Dhan historical service supports cash equities only; "
            "derivatives require explicit provider instrument classification"
        )
    if instrument.exchange is Exchange.NSE:
        return "NSE_EQ", "EQUITY"
    if instrument.exchange is Exchange.BSE:
        return "BSE_EQ", "EQUITY"
    raise UnsupportedDhanInstrumentError(
        f"unsupported Dhan cash exchange: {instrument.exchange.value}"
    )
