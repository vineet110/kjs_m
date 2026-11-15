"""browser extension: devices, one-time connect codes, site visits, hourly site blocks (with outcomes)

New tables only. No existing data changes.

Revision ID: 0029
Revises: 0028
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0029'
down_revision: Union[str, None] = '0028'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOW = sa.text('now()')


def user_fk():
    return sa.ForeignKey('users.id', ondelete='CASCADE')  # a new one per table (SQLAlchemy can't share one)


def upgrade() -> None:
    op.create_table(
        'extension_devices',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), user_fk(), nullable=False),
        sa.Column('name', sa.String(80), nullable=False),
        sa.Column('key_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True)),
        sa.Column('disabled_at', sa.DateTime(timezone=True)),
        sa.Column('disabled_by', sa.Integer(), sa.ForeignKey('users.id')),
    )
    op.create_index('ix_extension_devices_user', 'extension_devices', ['user_id'])

    op.create_table(
        'extension_pair_codes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), user_fk(), nullable=False),
        sa.Column('code_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True)),
    )

    op.create_table(
        'site_visits',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), user_fk(), nullable=False),
        sa.Column('device_id', sa.Integer(), sa.ForeignKey('extension_devices.id', ondelete='CASCADE'), nullable=False),
        sa.Column('client_id', sa.String(64), nullable=False),
        sa.Column('domain', sa.String(255), nullable=False),
        sa.Column('url', sa.String(2000), nullable=False),
        sa.Column('title', sa.String(300), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('seconds', sa.Integer(), nullable=False),
        sa.UniqueConstraint('device_id', 'client_id', name='uq_site_visits_device_client'),
    )
    op.create_index('ix_site_visits_user_started', 'site_visits', ['user_id', 'started_at'])

    op.create_table(
        'site_blocks',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), user_fk(), nullable=False),
        sa.Column('domain', sa.String(255), nullable=False),
        sa.Column('hour_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('seconds', sa.Integer(), nullable=False),
        sa.Column('outcome', sa.Text(), nullable=False, server_default=''),
        sa.Column('outcome_at', sa.DateTime(timezone=True)),
        sa.Column('reminded_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('user_id', 'domain', 'hour_start', name='uq_site_blocks_user_domain_hour'),
    )
    op.create_index('ix_site_blocks_user_hour', 'site_blocks', ['user_id', 'hour_start'])


def downgrade() -> None:
    op.drop_table('site_blocks')
    op.drop_table('site_visits')
    op.drop_table('extension_pair_codes')
    op.drop_table('extension_devices')
