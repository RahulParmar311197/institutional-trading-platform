import csv
import io
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trading_platform.instruments import InstrumentIdentifier

DHAN_PROVIDER = "dhan"
_REQUIRED_COMPACT_COLUMNS = frozenset(
    {
        "SEM_SMST_SECURITY_ID",
        "SEM_EXM_EXCH_ID",
        "SEM_SEGMENT",
        "SEM_INSTRUMENT_NAME",
        "SEM_EXPIRY_CODE",
    }
)
_SUPPORTED_EXCHANGES = frozenset({"NSE", "BSE"})
_KNOWN_SEGMENTS = frozenset({"C", "D", "E", "I", "M"})
_DERIVATIVE_TYPES = frozenset({"FUTIDX", "FUTSTK", "OPTIDX", "OPTSTK"})


class DhanInstrumentMasterError(ValueError):
    pass


class DhanInstrumentMasterConflictError(DhanInstrumentMasterError):
    pass


@dataclass(frozen=True, slots=True)
class DhanInstrumentMasterRecord:
    security_id: str
    exchange_segment: str
    instrument_type: str
    expiry_code: int | None


@dataclass(frozen=True, slots=True)
class DhanInstrumentMasterSyncResult:
    matched: int
    updated: int
    unchanged: int
    unmatched_identifiers: int


def parse_dhan_compact_instrument_master(
    content: str,
) -> tuple[DhanInstrumentMasterRecord, ...]:
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        raise DhanInstrumentMasterError("Dhan compact instrument master has no header")
    missing = _REQUIRED_COMPACT_COLUMNS.difference(reader.fieldnames)
    if missing:
        joined = ", ".join(sorted(missing))
        raise DhanInstrumentMasterError(
            f"Dhan compact instrument master missing required columns: {joined}"
        )

    by_security_id: dict[str, DhanInstrumentMasterRecord] = {}
    for row_number, row in enumerate(reader, start=2):
        exchange = _required_cell(row, "SEM_EXM_EXCH_ID", row_number).upper()
        segment = _required_cell(row, "SEM_SEGMENT", row_number).upper()
        if segment not in _KNOWN_SEGMENTS:
            raise DhanInstrumentMasterError(
                f"unsupported Dhan master segment {segment!r} on row {row_number}"
            )
        if exchange not in _SUPPORTED_EXCHANGES or segment not in {"D", "E"}:
            continue

        security_id = _required_cell(row, "SEM_SMST_SECURITY_ID", row_number)
        instrument_type = _required_cell(
            row,
            "SEM_INSTRUMENT_NAME",
            row_number,
        ).upper()
        exchange_segment = _exchange_segment(exchange, segment, row_number)
        _validate_instrument_type(segment, instrument_type, row_number)
        expiry_code = _parse_expiry_code(row.get("SEM_EXPIRY_CODE"), row_number)
        record = DhanInstrumentMasterRecord(
            security_id=security_id,
            exchange_segment=exchange_segment,
            instrument_type=instrument_type,
            expiry_code=expiry_code,
        )

        existing = by_security_id.get(security_id)
        if existing is not None and existing != record:
            raise DhanInstrumentMasterConflictError(
                f"conflicting Dhan master rows for security ID {security_id}"
            )
        by_security_id[security_id] = record

    return tuple(by_security_id.values())


class DhanInstrumentMasterSynchronizer:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def synchronize(
        self,
        records: tuple[DhanInstrumentMasterRecord, ...],
    ) -> DhanInstrumentMasterSyncResult:
        by_security_id = _index_records(records)
        result = await self.session.scalars(
            select(InstrumentIdentifier).where(
                InstrumentIdentifier.provider == DHAN_PROVIDER
            )
        )
        identifiers = tuple(result.all())

        proposed: list[
            tuple[InstrumentIdentifier, DhanInstrumentMasterRecord, bool]
        ] = []
        matched = 0
        unchanged = 0
        unmatched = 0

        for identifier in identifiers:
            record = by_security_id.get(identifier.external_id)
            if record is None:
                unmatched += 1
                continue
            matched += 1
            _validate_existing_metadata(identifier, record)
            needs_update = _needs_update(identifier, record)
            proposed.append((identifier, record, needs_update))
            if not needs_update:
                unchanged += 1

        updated = 0
        for identifier, record, needs_update in proposed:
            if not needs_update:
                continue
            identifier.provider_exchange_segment = record.exchange_segment
            identifier.provider_instrument_type = record.instrument_type
            if record.expiry_code is not None:
                identifier.provider_expiry_code = record.expiry_code
            updated += 1

        return DhanInstrumentMasterSyncResult(
            matched=matched,
            updated=updated,
            unchanged=unchanged,
            unmatched_identifiers=unmatched,
        )


def _index_records(
    records: tuple[DhanInstrumentMasterRecord, ...],
) -> dict[str, DhanInstrumentMasterRecord]:
    indexed: dict[str, DhanInstrumentMasterRecord] = {}
    for record in records:
        existing = indexed.get(record.security_id)
        if existing is not None and existing != record:
            raise DhanInstrumentMasterConflictError(
                f"conflicting Dhan master records for security ID {record.security_id}"
            )
        indexed[record.security_id] = record
    return indexed


def _required_cell(row: dict[str, str | None], column: str, row_number: int) -> str:
    value = row.get(column)
    if value is None or not value.strip():
        raise DhanInstrumentMasterError(
            f"Dhan master row {row_number} requires {column}"
        )
    return value.strip()


def _exchange_segment(exchange: str, segment: str, row_number: int) -> str:
    if segment == "E":
        return f"{exchange}_EQ"
    if segment == "D":
        return f"{exchange}_FNO"
    raise DhanInstrumentMasterError(
        f"unsupported Dhan master exchange/segment on row {row_number}"
    )


def _validate_instrument_type(
    segment: str,
    instrument_type: str,
    row_number: int,
) -> None:
    if segment == "E" and instrument_type != "EQUITY":
        raise DhanInstrumentMasterError(
            f"Dhan equity row {row_number} has invalid instrument {instrument_type!r}"
        )
    if segment == "D" and instrument_type not in _DERIVATIVE_TYPES:
        raise DhanInstrumentMasterError(
            f"Dhan derivative row {row_number} has invalid instrument {instrument_type!r}"
        )


def _parse_expiry_code(value: str | None, row_number: int) -> int | None:
    if value is None or not value.strip():
        return None
    try:
        numeric = Decimal(value.strip())
    except InvalidOperation as exc:
        raise DhanInstrumentMasterError(
            f"Dhan master row {row_number} has invalid expiry code"
        ) from exc
    if numeric != numeric.to_integral_value():
        raise DhanInstrumentMasterError(
            f"Dhan master row {row_number} has non-integer expiry code"
        )
    expiry_code = int(numeric)
    if expiry_code not in {0, 1, 2}:
        raise DhanInstrumentMasterError(
            f"Dhan master row {row_number} has unsupported expiry code {expiry_code}"
        )
    return expiry_code


def _validate_existing_metadata(
    identifier: InstrumentIdentifier,
    record: DhanInstrumentMasterRecord,
) -> None:
    conflicts = (
        (
            "provider_exchange_segment",
            identifier.provider_exchange_segment,
            record.exchange_segment,
        ),
        (
            "provider_instrument_type",
            identifier.provider_instrument_type,
            record.instrument_type,
        ),
        (
            "provider_expiry_code",
            identifier.provider_expiry_code,
            record.expiry_code,
        ),
    )
    for field_name, current, incoming in conflicts:
        if current is not None and incoming is not None and current != incoming:
            raise DhanInstrumentMasterConflictError(
                f"Dhan master conflicts with {field_name} for security ID "
                f"{identifier.external_id}: stored={current!r}, incoming={incoming!r}"
            )


def _needs_update(
    identifier: InstrumentIdentifier,
    record: DhanInstrumentMasterRecord,
) -> bool:
    if identifier.provider_exchange_segment is None:
        return True
    if identifier.provider_instrument_type is None:
        return True
    return record.expiry_code is not None and identifier.provider_expiry_code is None
