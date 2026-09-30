import uuid
from datetime import date

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from trading_platform.instruments import InstrumentIdentifier


class InstrumentIdentifierNotFoundError(LookupError):
    pass


class AmbiguousInstrumentIdentifierError(LookupError):
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
        normalized_provider = provider.strip()
        if not normalized_provider:
            raise ValueError("provider must not be empty")

        statement = select(InstrumentIdentifier.external_id).where(
            InstrumentIdentifier.instrument_id == instrument_id,
            InstrumentIdentifier.provider == normalized_provider,
            or_(
                InstrumentIdentifier.valid_from.is_(None),
                InstrumentIdentifier.valid_from <= on_date,
            ),
            or_(
                InstrumentIdentifier.valid_to.is_(None),
                InstrumentIdentifier.valid_to >= on_date,
            ),
        )
        identifiers = tuple((await self.session.scalars(statement)).all())
        if not identifiers:
            raise InstrumentIdentifierNotFoundError(
                f"no {normalized_provider} identifier for instrument {instrument_id} on {on_date}"
            )
        if len(identifiers) > 1:
            raise AmbiguousInstrumentIdentifierError(
                f"multiple {normalized_provider} identifiers for instrument {instrument_id} on {on_date}"
            )
        return identifiers[0]
