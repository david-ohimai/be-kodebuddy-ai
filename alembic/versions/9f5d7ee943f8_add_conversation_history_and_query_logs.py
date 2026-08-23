"""add conversation_history and query_logs

Revision ID: 9f5d7ee943f8
Revises: 3e2b6ce6147f
Create Date: 2026-08-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '9f5d7ee943f8'
down_revision: Union[str, Sequence[str], None] = '3e2b6ce6147f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('conversation_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('learner_id', sa.Integer(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('module_id', sa.Integer(), nullable=True),
    sa.Column('role', sa.Enum('USER', 'ASSISTANT', name='chatrole'), nullable=False),
    sa.Column('message', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
    sa.ForeignKeyConstraint(['learner_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['module_id'], ['modules.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_conversation_history_course_id'), 'conversation_history', ['course_id'], unique=False)
    op.create_index(op.f('ix_conversation_history_created_at'), 'conversation_history', ['created_at'], unique=False)
    op.create_index(op.f('ix_conversation_history_learner_id'), 'conversation_history', ['learner_id'], unique=False)
    op.create_index(op.f('ix_conversation_history_module_id'), 'conversation_history', ['module_id'], unique=False)

    op.create_table('query_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('learner_id', sa.Integer(), nullable=False),
    sa.Column('course_id', sa.Integer(), nullable=False),
    sa.Column('module_id', sa.Integer(), nullable=True),
    sa.Column('assignment_id', sa.Integer(), nullable=True),
    sa.Column('query_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('question', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('top_retrieval_score', sa.Float(), nullable=True),
    sa.Column('confidence_score', sa.Float(), nullable=False),
    sa.Column('is_confident', sa.Boolean(), nullable=False),
    sa.Column('escalated', sa.Boolean(), nullable=False),
    sa.Column('escalation_reason', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('escalation_detail', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('escalation_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['assignment_id'], ['assignments.id'], ),
    sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
    sa.ForeignKeyConstraint(['learner_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['module_id'], ['modules.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_query_logs_course_id'), 'query_logs', ['course_id'], unique=False)
    op.create_index(op.f('ix_query_logs_created_at'), 'query_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_query_logs_escalated'), 'query_logs', ['escalated'], unique=False)
    op.create_index(op.f('ix_query_logs_escalation_reason'), 'query_logs', ['escalation_reason'], unique=False)
    op.create_index(op.f('ix_query_logs_is_confident'), 'query_logs', ['is_confident'], unique=False)
    op.create_index(op.f('ix_query_logs_learner_id'), 'query_logs', ['learner_id'], unique=False)
    op.create_index(op.f('ix_query_logs_query_type'), 'query_logs', ['query_type'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_query_logs_query_type'), table_name='query_logs')
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
