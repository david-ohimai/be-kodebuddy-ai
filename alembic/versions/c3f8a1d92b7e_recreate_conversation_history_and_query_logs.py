"""recreate conversation_history and query_logs on the reconciled schema

Replaces the orphaned 9f5d7ee943f8 migration (deleted), which branched off
3e2b6ce6147f but was never merged into b7d3e9f1a2c4 -- it was a second,
undiscovered alembic head. It also declared the chatrole enum as
('USER', 'ASSISTANT'), which does not match ChatRole's actual lowercase
.value strings ("user"/"assistant"); every insert against that shape would
have failed. This migration creates both tables directly on the agreed
final schema (app/agent/model.py): ConversationHistory unchanged from
9f5d7ee943f8's intent, QueryLog as the reconciled Dev A/Dev E superset,
including retrieved_chunk_ids, latency_ms, and a real FK on escalation_id.

If a dev database already has these tables from running the orphaned
9f5d7ee943f8 migration directly, drop them (and clear their rows from
alembic_version if present) before running `alembic upgrade head`, since
that revision no longer exists in this history.

Revision ID: c3f8a1d92b7e
Revises: b7d3e9f1a2c4
Create Date: 2026-08-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'c3f8a1d92b7e'
down_revision: Union[str, Sequence[str], None] = 'b7d3e9f1a2c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 95bb2c9b27c6 (an ancestor of this revision -- the only path down to
    # it goes through 95bb2c9b27c6 -> ... -> b7d3e9f1a2c4 -> here) already
    # created both tables under the original, narrower column list.
    # Without dropping them first, the create_table calls below fail with
    # "relation already exists" on every database in this history, since
    # none of them can reach this revision without having applied
    # 95bb2c9b27c6 first.
    #
    # NOTE -- this drops and recreates both tables, so any existing
    # conversation_history/query_logs rows are lost. Acceptable for this
    # MVP (the agent request path has never successfully written to
    # either table yet, blocked by the app.agent.repository import bug
    # fixed alongside this migration), but flag it if either table has
    # picked up real rows by the time this runs.
    op.drop_table('query_logs')
    op.drop_table('conversation_history')

    op.create_table(
        'conversation_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('learner_id', sa.Integer(), nullable=False),
        sa.Column('course_id', sa.Integer(), nullable=False),
        sa.Column('module_id', sa.Integer(), nullable=True),
        sa.Column('role', sa.Enum('user', 'assistant', name='chatrole'), nullable=False),
        sa.Column('message', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
        sa.ForeignKeyConstraint(['learner_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['module_id'], ['modules.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_conversation_history_course_id'), 'conversation_history', ['course_id'], unique=False)
    op.create_index(op.f('ix_conversation_history_created_at'), 'conversation_history', ['created_at'], unique=False)
    op.create_index(op.f('ix_conversation_history_learner_id'), 'conversation_history', ['learner_id'], unique=False)
    op.create_index(op.f('ix_conversation_history_module_id'), 'conversation_history', ['module_id'], unique=False)

    op.create_table(
        'query_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('learner_id', sa.Integer(), nullable=False),
        sa.Column('course_id', sa.Integer(), nullable=False),
        sa.Column('module_id', sa.Integer(), nullable=True),
        sa.Column('assignment_id', sa.Integer(), nullable=True),
        sa.Column('query_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('question', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('retrieved_chunk_ids', sa.JSON(), nullable=False),
        sa.Column('top_retrieval_score', sa.Float(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('is_confident', sa.Boolean(), nullable=False),
        sa.Column('escalated', sa.Boolean(), nullable=False),
        sa.Column('escalation_reason', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('escalation_detail', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('escalation_id', sa.Integer(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['assignment_id'], ['assignments.id'], ),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
        sa.ForeignKeyConstraint(['escalation_id'], ['escalations.id'], ),
        sa.ForeignKeyConstraint(['learner_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['module_id'], ['modules.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_query_logs_course_id'), 'query_logs', ['course_id'], unique=False)
    op.create_index(op.f('ix_query_logs_created_at'), 'query_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_query_logs_escalated'), 'query_logs', ['escalated'], unique=False)
    op.create_index(op.f('ix_query_logs_escalation_reason'), 'query_logs', ['escalation_reason'], unique=False)
    op.create_index(op.f('ix_query_logs_is_confident'), 'query_logs', ['is_confident'], unique=False)
    op.create_index(op.f('ix_query_logs_learner_id'), 'query_logs', ['learner_id'], unique=False)
    op.create_index(op.f('ix_query_logs_module_id'), 'query_logs', ['module_id'], unique=False)
    op.create_index(op.f('ix_query_logs_assignment_id'), 'query_logs', ['assignment_id'], unique=False)
    op.create_index(op.f('ix_query_logs_query_type'), 'query_logs', ['query_type'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_query_logs_query_type'), table_name='query_logs')
    op.drop_index(op.f('ix_query_logs_assignment_id'), table_name='query_logs')
    op.drop_index(op.f('ix_query_logs_module_id'), table_name='query_logs')
    op.drop_index(op.f('ix_query_logs_learner_id'), table_name='query_logs')
    op.drop_index(op.f('ix_query_logs_is_confident'), table_name='query_logs')
    op.drop_index(op.f('ix_query_logs_escalation_reason'), table_name='query_logs')
    op.drop_index(op.f('ix_query_logs_escalated'), table_name='query_logs')
    op.drop_index(op.f('ix_query_logs_created_at'), table_name='query_logs')
    op.drop_index(op.f('ix_query_logs_course_id'), table_name='query_logs')
    op.drop_table('query_logs')

    op.drop_index(op.f('ix_conversation_history_module_id'), table_name='conversation_history')
    op.drop_index(op.f('ix_conversation_history_learner_id'), table_name='conversation_history')
    op.drop_index(op.f('ix_conversation_history_created_at'), table_name='conversation_history')
    op.drop_index(op.f('ix_conversation_history_course_id'), table_name='conversation_history')
    op.drop_table('conversation_history')
    sa.Enum(name='chatrole').drop(op.get_bind(), checkfirst=True)