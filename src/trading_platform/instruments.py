import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from trading_platform.models import Base


class Exchange(StrEnum):
    NSE = "NSE"
    BSE = "BSE"


class Segment(StrEnum):
    CASH = "CASH"
    FUTURES = "FUTURES"
    OPTIONS = "OPTIONS"


class OptionType(StrEnum):
    CALL = "CALL"
    PUT = "PUT"


class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = (
        UniqueConstraint(
            "exchange",
            "segment",
            "trading_symbol",
            "expiry",
            "strike",
            "option_type",
            name="uq_instrument_contract",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    exchange: Mapped[Exchange] = mapped_column(
        Enum(Exchange, name="exchange_enum"), nullable=False
    )
    segment: Mapped[Segment] = mapped_column(
        Enum(Segment, name="segment_enum"), nullable=False
    )
    trading_symbol: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    isin: Mapped[str | None] = mapped_column(String(20))
    underlying_symbol: Mapped[str | None] = mapped_column(String(100), index=True)
    expiry: Mapped[date | None] = mapped_column(Date)
    strike: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    option_type: Mapped[OptionType | None] = mapped_column(
        Enum(OptionType, name="option_type_enum")
    )
    lot_size: Mapped[int] = mapped_column(nullable=False, default=1)
    tick_size: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    identifiers: Mapped[list["InstrumentIdentifier"]] = relationship(
        back_populates="instrument", cascade="all, delete-orphan"
    )


class InstrumentIdentifier(Base):
    __tablename__ = "instrument_identifiers"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "external_id",
            name="uq_instrument_provider_external_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("instruments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    provider_exchange_segment: Mapped[str | None] = mapped_column(String(50))
    provider_instrument_type: Mapped[str | None] = mapped_column(String(50))
    provider_expiry_code: Mapped[int | None] = mapped_column(Integer)

    instrument: Mapped[Instrument] = relationship(back_populates="identifiers")
