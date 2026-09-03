"""add response columns to escalations

Revision ID: 56a8303347fa
Revises: a1c2e3f4b5d6
Create Date: 2026-09-03 03:00:00.000000

Trainer replies were previously appended into `detail`, which is the
agent's own field (why it wasn't confident) -- overwriting/concatenating a
trainer's reply onto that made the two impossible to tell apart, and after
more than one reply produced an unstructured blob with no timestamp.

This adds two nullable columns, additive and safe against existing rows
(pre-existing escalations simply have NULL here):

    response       text        (the trainer's reply, replacing the old
                                 "Trainer response: ..." suffix on `detail`)
    responded_at   timestamptz (when `response` was last written; overwritten,
                                 not appended, on every subsequent PATCH)

Written by app/features/escalations/repository.py::EscalationRepository.update,
via PATCH /escalations/{escalation_id} (trainer-only). Read by the new
learner-facing GET /escalations/learner and GET /escalations/{escalation_id}
routes, and returned on EscalationResponse.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '56a8303347fa'
down_revision: Union[str, Sequence[str], None] = 'a1c2e3f4b5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'escalations',
        sa.Column('response', sa.Text(), nullable=True),
    )
    op.add_column(
        'escalations',
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('escalations', 'responded_at')
    op.drop_column('escalations', 'response')