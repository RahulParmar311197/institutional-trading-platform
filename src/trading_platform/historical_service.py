import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from trading_platform.instrument_identifiers import InstrumentIdentifierRepository
from trading_platform.provider_historical import (
    HistoricalBar,
    UpstoxHistoricalClient,
    UpstoxHistoricalUnit,
)

UPSTOX_PROVIDER = "upstox"


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
