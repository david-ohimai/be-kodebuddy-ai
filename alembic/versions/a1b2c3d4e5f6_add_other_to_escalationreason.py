"""add OTHER value to escalationreason enum

Revision ID: a1b2c3d4e5f6
Revises: f0f069aa67b5
Create Date: 2026-09-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "f0f069aa67b5"
branch_labels = None
depends_on = None

def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE escalationreason ADD VALUE IF NOT EXISTS 'other'"
        )


def downgrade() -> None:
    pass