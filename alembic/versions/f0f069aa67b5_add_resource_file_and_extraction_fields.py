"""add resource file and extraction fields

Revision ID: f0f069aa67b5
Revises: 5840e2e0980f
Create Date: 2026-09-08 13:45:12.144917

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f0f069aa67b5'
down_revision: Union[str, Sequence[str], None] = '5840e2e0980f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "resources",
        sa.Column("file_path", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "resources",
        sa.Column("file_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "resources",
        sa.Column("mime_type", sa.String(length=127), nullable=True),
    )
    op.add_column(
        "resources",
        sa.Column("content_extract_status", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "resources",
        sa.Column("content_extract_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("resources", "content_extract_error")
    op.drop_column("resources", "content_extract_status")
    op.drop_column("resources", "mime_type")
    op.drop_column("resources", "file_name")
    op.drop_column("resources", "file_path")