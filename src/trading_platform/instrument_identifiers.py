import uuid
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from trading_platform.instruments import InstrumentIdentifier


class InstrumentIdentifierNotFoundError(LookupError):
    pass


class AmbiguousInstrumentIdentifierError(LookupError):
    pass


class InstrumentIdentifierRangeNotCoveredError(LookupError):
    pass


class InstrumentIdentifierRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def resolve(
        self,
        *,
        instrument_id: uuid.UUID,
        provider: str,
        on_date: date,
    ) -> str:
        normalized_provider = self._normalize_provider(provider)
        identifiers = await self._matching_identifiers(
            instrument_id=instrument_id,
            provider=normalized_provider,
            start_date=on_date,
            end_date=on_date,
        )
        if not identifiers:
            raise InstrumentIdentifierNotFoundError(
                f"no {normalized_provider} identifier for instrument "
                f"{instrument_id} on {on_date}"
            )
        if len(identifiers) > 1:
            raise AmbiguousInstrumentIdentifierError(
                f"multiple {normalized_provider} identifiers for instrument "
                f"{instrument_id} on {on_date}"
            )
        return identifiers[0]

    async def resolve_range(
        self,
        *,
        instrument_id: uuid.UUID,
        provider: str,
        start_date: date,
        end_date: date,
    ) -> str:
        if start_date > end_date:
            raise ValueError("start_date must not be after end_date")
        normalized_provider = self._normalize_provider(provider)
        identifiers = await self._matching_identifiers(
            instrument_id=instrument_id,
            provider=normalized_provider,
            start_date=start_date,
            end_date=end_date,
        )
        if not identifiers:
            raise InstrumentIdentifierRangeNotCoveredError(
                f"no single {normalized_provider} identifier covers instrument "
                f"{instrument_id} from {start_date} through {end_date}"
            )
        if len(identifiers) > 1:
            raise AmbiguousInstrumentIdentifierError(
                f"multiple {normalized_provider} identifiers cover instrument "
                f"{instrument_id} from {start_date} through {end_date}"
            )
        return identifiers[0]

    @staticmethod
    def _normalize_provider(provider: str) -> str:
        normalized_provider = provider.strip()
        if not normalized_provider:
            raise ValueError("provider must not be empty")
        return normalized_provider

    async def _matching_identifiers(
        self,
        *,
        instrument_id: uuid.UUID,
        provider: str,
        start_date: date,
        end_date: date,
    ) -> tuple[str, ...]:
        statement = select(InstrumentIdentifier.external_id).where(
            InstrumentIdentifier.instrument_id == instrument_id,
            InstrumentIdentifier.provider == provider,
            or_(
                InstrumentIdentifier.valid_from.is_(None),
                InstrumentIdentifier.valid_from <= start_date,
            ),
            or_(
                InstrumentIdentifier.valid_to.is_(None),
                InstrumentIdentifier.valid_to >= end_date,
            ),
        )
        return tuple((await self.session.scalars(statement)).all())
