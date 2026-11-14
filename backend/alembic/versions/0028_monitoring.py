"""monitoring: screenshots, screen-sharing events, breaks, idle periods; attendance device + break alert

New tables only, plus two empty columns on attendance. No existing data changes.

Revision ID: 0028
Revises: 0027
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0028'
down_revision: Union[str, None] = '0027'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

USER = sa.ForeignKey('users.id', ondelete='CASCADE')
NOW = sa.text('now()')


def upgrade() -> None:
    op.create_table(
        'screenshots',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), USER, nullable=False),
        sa.Column('taken_at', sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column('storage_key', sa.String(200), nullable=False, unique=True),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(10), nullable=False),
    )
    op.create_index('ix_screenshots_user_taken', 'screenshots', ['user_id', 'taken_at'])
    op.create_index('ix_screenshots_taken', 'screenshots', ['taken_at'])

    op.create_table(
        'share_events',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), USER, nullable=False),
        sa.Column('at', sa.DateTime(timezone=True), server_default=NOW, nullable=False),
        sa.Column('state', sa.String(10), nullable=False),
        sa.Column('source', sa.String(10), nullable=False),
        sa.Column('alerted_at', sa.DateTime(timezone=True)),
        sa.CheckConstraint("state IN ('started', 'stopped', 'refused')", name='ck_share_events_state'),
    )
    op.create_index('ix_share_events_user_at', 'share_events', ['user_id', 'at'])

    op.create_table(
        'breaks',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), USER, nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_breaks_user_day', 'breaks', ['user_id', 'day'])
    # At most one open break per person (two quick clicks can't start two)
    op.create_index('uq_breaks_one_open', 'breaks', ['user_id'], unique=True,
                    postgresql_where=sa.text('ended_at IS NULL'))

    op.create_table(
        'idle_periods',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), USER, nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True)),
        sa.Column('reason', sa.String(20), nullable=False, server_default=''),
        sa.Column('reason_note', sa.String(200), nullable=False, server_default=''),
        sa.Column('warned_at', sa.DateTime(timezone=True)),
        sa.Column('admin_alerted_at', sa.DateTime(timezone=True)),
    )
    op.create_index('ix_idle_periods_user_started', 'idle_periods', ['user_id', 'started_at'])
    op.create_index('uq_idle_periods_one_open', 'idle_periods', ['user_id'], unique=True,
                    postgresql_where=sa.text('ended_at IS NULL'))

    op.add_column('attendance', sa.Column('device', sa.String(10)))  # laptop | phone (set at check-in)
    op.add_column('attendance', sa.Column('break_alerted_at', sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column('attendance', 'break_alerted_at')
    op.drop_column('attendance', 'device')
    op.drop_table('idle_periods')
    op.drop_table('breaks')
    op.drop_table('share_events')
    op.drop_table('screenshots')
