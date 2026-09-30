import uuid
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from trading_platform.instrument_identifiers import (
    InstrumentIdentifierRepository,
    ProviderInstrumentReference,
)
from trading_platform.instruments import Exchange, Instrument, Segment
from trading_platform.provider_historical import (
    DhanHistoricalClient,
    HistoricalBar,
    UpstoxHistoricalClient,
    UpstoxHistoricalUnit,
)

UPSTOX_PROVIDER = "upstox"
DHAN_PROVIDER = "dhan"
_DHAN_DERIVATIVE_EXPIRY_CODES = frozenset({0, 1, 2})
_DHAN_FUTURE_INSTRUMENT_TYPES = frozenset({"FUTIDX", "FUTSTK"})
_DHAN_OPTION_INSTRUMENT_TYPES = frozenset({"OPTIDX", "OPTSTK"})


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
        include_open_interest: bool = False,
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
            reference = await InstrumentIdentifierRepository(
                session
            ).resolve_reference_range(
                instrument_id=instrument_id,
                provider=DHAN_PROVIDER,
                start_date=from_date,
                end_date=coverage_end,
            )
            exchange_segment, instrument_type, expiry_code = _dhan_classification(
                instrument,
                reference,
            )

        return await self.client.fetch_daily(
            security_id=reference.external_id,
            exchange_segment=exchange_segment,
            instrument=instrument_type,
            from_date=from_date,
            to_date=to_date,
            expiry_code=expiry_code,
            include_open_interest=include_open_interest,
        )


def _dhan_classification(
    instrument: Instrument,
    reference: ProviderInstrumentReference,
) -> tuple[str, str, int]:
    if instrument.segment is Segment.CASH:
        if instrument.exchange is Exchange.NSE:
            return "NSE_EQ", "EQUITY", 0
        if instrument.exchange is Exchange.BSE:
            return "BSE_EQ", "EQUITY", 0
        raise UnsupportedDhanInstrumentError(
            f"unsupported Dhan cash exchange: {instrument.exchange.value}"
        )

    expected_exchange_segment = {
        Exchange.NSE: "NSE_FNO",
        Exchange.BSE: "BSE_FNO",
    }.get(instrument.exchange)
    if expected_exchange_segment is None:
        raise UnsupportedDhanInstrumentError(
            f"unsupported Dhan derivative exchange: {instrument.exchange.value}"
        )
    if reference.exchange_segment != expected_exchange_segment:
        raise UnsupportedDhanInstrumentError(
            "Dhan derivative identifier requires explicit exchange segment "
            f"{expected_exchange_segment}"
        )

    if instrument.segment is Segment.FUTURES:
        allowed_types = _DHAN_FUTURE_INSTRUMENT_TYPES
    elif instrument.segment is Segment.OPTIONS:
        allowed_types = _DHAN_OPTION_INSTRUMENT_TYPES
    else:
        raise UnsupportedDhanInstrumentError(
            f"unsupported Dhan canonical segment: {instrument.segment.value}"
        )
    if reference.instrument_type not in allowed_types:
        expected = ", ".join(sorted(allowed_types))
        raise UnsupportedDhanInstrumentError(
            "Dhan derivative identifier requires explicit instrument type; "
            f"expected one of {expected}"
        )
    if reference.expiry_code not in _DHAN_DERIVATIVE_EXPIRY_CODES:
        raise UnsupportedDhanInstrumentError(
            "Dhan derivative identifier requires explicit expiry code 0, 1, or 2"
        )

    return (
        expected_exchange_segment,
        reference.instrument_type,
        reference.expiry_code,
    )
