"""add provider instrument classification

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "instrument_identifiers",
        sa.Column("provider_exchange_segment", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "instrument_identifiers",
        sa.Column("provider_instrument_type", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "instrument_identifiers",
        sa.Column("provider_expiry_code", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("instrument_identifiers", "provider_expiry_code")
    op.drop_column("instrument_identifiers", "provider_instrument_type")
    op.drop_column("instrument_identifiers", "provider_exchange_segment")
