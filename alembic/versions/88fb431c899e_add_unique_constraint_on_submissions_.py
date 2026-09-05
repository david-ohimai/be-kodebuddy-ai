"""add unique constraint on submissions assignment+learner

Revision ID: 88fb431c899e
Revises: 73e41adf5604
Create Date: 2026-09-04 23:30:03.212406

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '88fb431c899e'
down_revision: Union[str, Sequence[str], None] = '73e41adf5604'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_unique_constraint('uq_submission_assignment_learner', 'submissions',['assignment_id', 'learner_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_submission_assignment_learner', 'submissions', type_='unique')
