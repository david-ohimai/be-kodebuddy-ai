"""add module active status

Revision ID: a9728dde9497
Revises: a47c4b2dbaff
Create Date: 2026-08-19 06:02:46.956733

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9728dde9497'
down_revision: Union[str, Sequence[str], None] = 'a47c4b2dbaff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_active column to modules table."""

    op.add_column(
        "modules",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )

    op.create_index(
        "ix_modules_is_active",
        "modules",
        ["is_active"],
        unique=False,
    )


def downgrade() -> None:
    """Remove is_active column from modules table."""

    op.drop_index(
        "ix_modules_is_active",
        table_name="modules",
    )

    op.drop_column(
        "modules",
        "is_active",
    )