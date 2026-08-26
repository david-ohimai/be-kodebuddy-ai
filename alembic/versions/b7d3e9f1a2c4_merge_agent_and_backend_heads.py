"""merge_agent_and_backend_heads

Revision ID: b7d3e9f1a2c4
Revises: d9ca6ddfa78b, f3a9c1d84b2e
Create Date: 2026-08-25 12:00:00.000000

Recreates a merge migration that was already applied to the dev database
(alembic_version = b7d3e9f1a2c4) but whose file never made it into the
dev branch — reconciles the two chains that both branched off
3e2b6ce6147f: Dev A's agent-tables chain (95bb2c9b27c6 -> f3a9c1d84b2e)
and the backend's chain (726948f7e3a8 -> d9ca6ddfa78b).

IMPORTANT: this revision ID must stay exactly 'b7d3e9f1a2c4' — any local
database already stamped at this revision (via a prior `alembic upgrade
head` before this file was lost) depends on a file with this exact ID
existing, or `alembic current`/`alembic heads` will fail to resolve it.
No schema changes of its own.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7d3e9f1a2c4'
down_revision: Union[str, Sequence[str], None] = ('d9ca6ddfa78b', 'f3a9c1d84b2e')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass