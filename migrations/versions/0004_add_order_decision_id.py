"""add order decision id

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("decision_id", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_index("ix_orders_decision_id", "orders", ["decision_id"])


def downgrade() -> None:
    op.drop_index("ix_orders_decision_id", table_name="orders")
    op.drop_column("orders", "decision_id")
