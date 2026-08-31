"""add start_date to assignments

Adds the "opens at" date the learner-facing assignment cards need in order to
render the Pending / Locked state. NULL means the assignment is already open,
which is how every existing row behaved before this column, so no backfill is
required and the change is safe to apply to a populated table.

Revision ID: b7d2e4f61a03
Revises: c1ae3a148bd3
Create Date: 2026-08-31

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7d2e4f61a03"
down_revision: Union[str, Sequence[str], None] = "c1ae3a148bd3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "assignments",
        sa.Column(
            "start_date",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("assignments", "start_date")
