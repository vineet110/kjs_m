"""attendance + regularizations

Revision ID: 0003
Revises: 0002
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0003'
down_revision: Union[str, None] = '0002'
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
    op.create_table(
        'attendance',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('check_in_at', sa.DateTime(timezone=True)),
        sa.Column('check_out_at', sa.DateTime(timezone=True)),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('source', sa.String(20), nullable=False),
        *_stamps(),
        sa.UniqueConstraint('user_id', 'day'),
    )
    op.create_index('ix_attendance_user_id', 'attendance', ['user_id'])
    op.create_index('ix_attendance_day', 'attendance', ['day'])
    op.create_table(
        'regularizations',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('check_in_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('check_out_at', sa.DateTime(timezone=True)),
        sa.Column('reason', sa.String(500), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('decided_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('decided_at', sa.DateTime(timezone=True)),
        *_stamps(),
    )
    op.create_index('ix_regularizations_user_id', 'regularizations', ['user_id'])
    op.create_index('ix_regularizations_status', 'regularizations', ['status'])


def downgrade() -> None:
    op.drop_table('regularizations')
    op.drop_table('attendance')
