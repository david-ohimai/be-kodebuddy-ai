"""merge migration heads

Revision ID: 3e2b6ce6147f
Revises: 5bade243b19a, eb15e00972e6
Create Date: 2026-08-24 09:10:56.393717

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3e2b6ce6147f'
down_revision: Union[str, Sequence[str], None] = ('5bade243b19a', 'eb15e00972e6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
