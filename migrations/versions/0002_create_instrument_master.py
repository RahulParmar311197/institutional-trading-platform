"""create instrument master

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    exchange = sa.Enum("NSE", "BSE", name="exchange_enum")
    segment = sa.Enum("CASH", "FUTURES", "OPTIONS", name="segment_enum")
    option_type = sa.Enum("CALL", "PUT", name="option_type_enum")
    exchange.create(op.get_bind(), checkfirst=True)
    segment.create(op.get_bind(), checkfirst=True)
    option_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "instruments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exchange", exchange, nullable=False),
        sa.Column("segment", segment, nullable=False),
        sa.Column("trading_symbol", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("isin", sa.String(20)),
        sa.Column("underlying_symbol", sa.String(100)),
        sa.Column("expiry", sa.Date()),
        sa.Column("strike", sa.Numeric(20, 8)),
        sa.Column("option_type", option_type),
        sa.Column("lot_size", sa.Integer(), nullable=False),
        sa.Column("tick_size", sa.Numeric(20, 8), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "exchange",
            "segment",
            "trading_symbol",
            "expiry",
            "strike",
            "option_type",
            name="uq_instrument_contract",
        ),
    )
    op.create_index("ix_instruments_trading_symbol", "instruments", ["trading_symbol"])
    op.create_index(
        "ix_instruments_underlying_symbol",
        "instruments",
        ["underlying_symbol"],
    )

    op.create_table(
        "instrument_identifiers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column("valid_from", sa.Date()),
        sa.Column("valid_to", sa.Date()),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "external_id",
            name="uq_instrument_provider_external_id",
        ),
    )
    op.create_index(
        "ix_instrument_identifiers_instrument_id",
        "instrument_identifiers",
        ["instrument_id"],
    )


def downgrade() -> None:
    op.drop_table("instrument_identifiers")
    op.drop_table("instruments")
    sa.Enum(name="option_type_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="segment_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="exchange_enum").drop(op.get_bind(), checkfirst=True)
