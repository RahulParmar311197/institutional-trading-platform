import uuid
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class ProviderInstrumentReference:
    external_id: str
    exchange_segment: str | None
    instrument_type: str | None
    expiry_code: int | None


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
        reference = await self.resolve_reference_range(
            instrument_id=instrument_id,
            provider=provider,
            start_date=on_date,
            end_date=on_date,
            not_found_error=InstrumentIdentifierNotFoundError,
        )
        return reference.external_id

    async def resolve_range(
        self,
        *,
        instrument_id: uuid.UUID,
        provider: str,
        start_date: date,
        end_date: date,
    ) -> str:
        reference = await self.resolve_reference_range(
            instrument_id=instrument_id,
            provider=provider,
            start_date=start_date,
            end_date=end_date,
        )
        return reference.external_id

    async def resolve_reference_range(
        self,
        *,
        instrument_id: uuid.UUID,
        provider: str,
        start_date: date,
        end_date: date,
        not_found_error: type[LookupError] = InstrumentIdentifierRangeNotCoveredError,
    ) -> ProviderInstrumentReference:
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
            if not_found_error is InstrumentIdentifierNotFoundError and start_date == end_date:
                raise not_found_error(
                    f"no {normalized_provider} identifier for instrument "
                    f"{instrument_id} on {start_date}"
                )
            raise not_found_error(
                f"no single {normalized_provider} identifier covers instrument "
                f"{instrument_id} from {start_date} through {end_date}"
            )
        if len(identifiers) > 1:
            if start_date == end_date:
                raise AmbiguousInstrumentIdentifierError(
                    f"multiple {normalized_provider} identifiers for instrument "
                    f"{instrument_id} on {start_date}"
                )
            raise AmbiguousInstrumentIdentifierError(
                f"multiple {normalized_provider} identifiers cover instrument "
                f"{instrument_id} from {start_date} through {end_date}"
            )
        identifier = identifiers[0]
        return ProviderInstrumentReference(
            external_id=identifier.external_id,
            exchange_segment=identifier.provider_exchange_segment,
            instrument_type=identifier.provider_instrument_type,
            expiry_code=identifier.provider_expiry_code,
        )

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
    ) -> tuple[InstrumentIdentifier, ...]:
        statement = select(InstrumentIdentifier).where(
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
