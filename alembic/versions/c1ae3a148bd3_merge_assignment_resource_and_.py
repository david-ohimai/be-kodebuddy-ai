"""merge assignment_resource and conversation_history heads

Revision ID: c1ae3a148bd3
Revises: c3f8a1d92b7e, babff2f0f73c
Create Date: 2026-08-28 14:06:11.477364

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1ae3a148bd3'
down_revision: Union[str, Sequence[str], None] = ('c3f8a1d92b7e', 'babff2f0f73c')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
