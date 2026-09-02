"""add start date to assignments

Revision ID: ba5c38169c4d
Revises: e0890556db40
Create Date: 2026-09-02 03:32:24.791625

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ba5c38169c4d'
down_revision: Union[str, Sequence[str], None] = 'e0890556db40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass



def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column("assignments", "start_date") 
