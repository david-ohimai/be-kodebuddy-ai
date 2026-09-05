"""add context columns to escalations

Revision ID: a1c2e3f4b5d6
Revises: d4e1f9a2b6c8
Create Date: 2026-09-03 02:00:00.000000

Escalations previously carried only (learner_id, course_id, trainer_id,
question, reason, detail, status) -- enough to know *that* a learner asked
something the agent couldn't confidently answer, but not enough for a
trainer to see what the agent actually attempted, how confident it was, or
which module/assignment the question came from.

This adds four nullable columns, all additive (safe against existing rows,
no backfill required -- pre-existing escalations simply have NULL here):

    module_id         -> modules.id      (nullable: not every CHAT question
                                           is module-scoped)
    assignment_id     -> assignments.id  (nullable: only set for
                                           ASSIGNMENT_GUIDANCE turns)
    draft_response     text              (the agent's own best-effort
                                           answer, when it had one and it was
                                           safe to show -- see
                                           app/agent/graph/nodes.py::route)
    confidence_score    float            (the graph's confidence_score for
                                           that draft, 0.0-1.0)

Written going forward by app/agent/router.py::create_escalation via
app/agent/repository.py::AgentRepository.create_escalation, whose INSERT
statement is updated in the same change as this migration to populate them.
The frontend sources module_id/assignment_id/draft_response/confidence_score
straight from the POST /agent/chat request/response it already has -- the
learner never re-types anything.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c2e3f4b5d6'
down_revision: Union[str, Sequence[str], None] = 'd4e1f9a2b6c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'escalations',
        sa.Column('module_id', sa.Integer(), nullable=True),
    )
    op.add_column(
        'escalations',
        sa.Column('assignment_id', sa.Integer(), nullable=True),
    )
    op.add_column(
        'escalations',
        sa.Column('draft_response', sa.Text(), nullable=True),
    )
    op.add_column(
        'escalations',
        sa.Column('confidence_score', sa.Float(), nullable=True),
    )

    op.create_foreign_key(
        'fk_escalations_module_id_modules',
        'escalations', 'modules',
        ['module_id'], ['id'],
    )
    op.create_foreign_key(
        'fk_escalations_assignment_id_assignments',
        'escalations', 'assignments',
        ['assignment_id'], ['id'],
    )
    op.create_index(
        op.f('ix_escalations_module_id'), 'escalations', ['module_id'], unique=False
    )
    op.create_index(
        op.f('ix_escalations_assignment_id'), 'escalations', ['assignment_id'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_escalations_assignment_id'), table_name='escalations')
    op.drop_index(op.f('ix_escalations_module_id'), table_name='escalations')
    op.drop_constraint('fk_escalations_assignment_id_assignments', 'escalations', type_='foreignkey')
    op.drop_constraint('fk_escalations_module_id_modules', 'escalations', type_='foreignkey')
    op.drop_column('escalations', 'confidence_score')
    op.drop_column('escalations', 'draft_response')
    op.drop_column('escalations', 'assignment_id')
    op.drop_column('escalations', 'module_id')