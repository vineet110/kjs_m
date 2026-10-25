"""lead SLA fields, lead notes, notifications, notification preferences

Revision ID: 0004
Revises: 0003
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _stamps():
    return [
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    ]


def upgrade() -> None:
    op.add_column('leads', sa.Column('responded_at', sa.DateTime(timezone=True)))
    op.add_column('leads', sa.Column('resolved_at', sa.DateTime(timezone=True)))
    op.add_column('leads', sa.Column('outcome', sa.String(40), nullable=False, server_default=''))
    op.add_column('leads', sa.Column('escalation_level', sa.Integer(), nullable=False, server_default='0'))
    op.create_index('ix_leads_assigned_to', 'leads', ['assigned_to'])
    op.add_column('users', sa.Column('notify_email', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('users', sa.Column('notify_whatsapp', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        'lead_notes',
        sa.Column('lead_id', sa.Integer(), sa.ForeignKey('leads.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('kind', sa.String(20), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        *_stamps(),
    )
    op.create_index('ix_lead_notes_lead_id', 'lead_notes', ['lead_id'])
    op.create_table(
        'notifications',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kind', sa.String(40), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('link', sa.String(255), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True)),
        sa.Column('email_status', sa.String(20), nullable=False),
        *_stamps(),
    )
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'])
    op.create_index('ix_notifications_email_status', 'notifications', ['email_status'])


def downgrade() -> None:
    op.drop_table('notifications')
    op.drop_table('lead_notes')
    op.drop_column('users', 'notify_whatsapp')
    op.drop_column('users', 'notify_email')
    op.drop_index('ix_leads_assigned_to', table_name='leads')
    for c in ('escalation_level', 'outcome', 'resolved_at', 'responded_at'):
        op.drop_column('leads', c)
