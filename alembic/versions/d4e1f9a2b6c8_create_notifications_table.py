"""create notifications table

Revision ID: d4e1f9a2b6c8
Revises: ba5c38169c4d
Create Date: 2026-09-03 01:00:00.000000

app/features/notifications/model.py (Notification/NotificationType) has
existed and been imported/used since the escalations feature landed, but no
migration ever created its backing table -- there is no earlier
`create_table('notifications', ...)` anywhere in this history. Confirmed by
running check_alembic_chain.py's own graph-walk logic against the current
alembic/versions/ tree: there is exactly one real head, ba5c38169c4d
(add_start_date_to_assignments), so this is safe to chain directly onto it.
(Note: check_alembic_chain.py itself currently misreports "0 migration
files" / "no head found" on this repo -- its `_extract_revision_vars` only
recognises plain `ast.Assign` nodes, but every file in this directory
declares `revision: str = '...'` as an annotated assignment (`ast.AnnAssign`),
so every file is silently skipped. Worth a one-line fix there separately;
not addressed in this migration.)

Every write to this table happens through NotificationRepository.create()
(app/features/notifications/repository.py), which never sets `is_read` or
`created_at` itself -- both rely on this table's own defaults, so both are
declared server-side here (`server_default`) rather than only as an ORM
default, matching how `created_at`/`updated_at` are handled on the
`escalations` table (see 95bb2c9b27c6's docstring reasoning in
app/agent/repository.py::create_escalation) so a raw INSERT that bypasses
the ORM still gets a valid row.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'd4e1f9a2b6c8'
down_revision: Union[str, Sequence[str], None] = 'ba5c38169c4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('message', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            'notification_type',
            sa.Enum(
                'escalation_created',
                'escalation_updated',
                'escalation_resolved',
                'escalation_assigned',
                name='notificationtype',
            ),
            nullable=False,
        ),
        sa.Column('related_entity_type', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True),
        sa.Column('related_entity_id', sa.Integer(), nullable=True),
        sa.Column('is_read', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)
    op.create_index(op.f('ix_notifications_notification_type'), 'notifications', ['notification_type'], unique=False)
    op.create_index(op.f('ix_notifications_related_entity_id'), 'notifications', ['related_entity_id'], unique=False)
    op.create_index(op.f('ix_notifications_is_read'), 'notifications', ['is_read'], unique=False)
    op.create_index(op.f('ix_notifications_created_at'), 'notifications', ['created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_notifications_created_at'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_is_read'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_related_entity_id'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_notification_type'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_table('notifications')
    sa.Enum(name='notificationtype').drop(op.get_bind(), checkfirst=True)
