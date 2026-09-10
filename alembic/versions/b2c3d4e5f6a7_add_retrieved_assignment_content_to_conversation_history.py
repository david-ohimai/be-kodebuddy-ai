"""add retrieved_assignment_content to conversation_history

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversation_history",
        sa.Column(
            "retrieved_assignment_content",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column("conversation_history", "retrieved_assignment_content", server_default=None)


def downgrade() -> None:
    op.drop_column("conversation_history", "retrieved_assignment_content")