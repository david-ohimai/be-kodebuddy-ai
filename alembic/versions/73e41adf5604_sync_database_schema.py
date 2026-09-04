"""sync database schema

Revision ID: 73e41adf5604
Revises: 56a8303347fa
Create Date: 2026-09-04 09:20:50.801941

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '73e41adf5604'
down_revision: Union[str, Sequence[str], None] = '56a8303347fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass