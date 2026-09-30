"""initialize persistent operational state

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO operational_state (id, mode)
            VALUES (1, 'NORMAL')
            ON CONFLICT (id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    # This is intentionally a no-op. The migration establishes a persistent singleton
    # state invariant, and deleting an operator-modified safety mode during downgrade
    # would be an unsafe data-loss side effect.
    pass
