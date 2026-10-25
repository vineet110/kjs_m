"""order board steps and members

Revision ID: 0007
Revises: 0006
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0007'
down_revision: Union[str, None] = '0006'
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
    op.add_column('order_boards', sa.Column('notes', sa.Text(), nullable=False, server_default=''))
    op.add_column('order_boards', sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id')))
    op.create_table(
        'board_steps',
        sa.Column('board_id', sa.Integer(), sa.ForeignKey('order_boards.id', ondelete='CASCADE'), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('percent', sa.Integer()),
        sa.Column('days', sa.Integer()),
        sa.Column('planned_start', sa.Date(), nullable=False),
        sa.Column('planned_end', sa.Date(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('done_at', sa.DateTime(timezone=True)),
        sa.Column('task_templates', postgresql.JSONB(), nullable=False),
        sa.Column('checklist', postgresql.JSONB(), nullable=False),
        sa.Column('alerted_pct', sa.Integer(), nullable=False),
        *_stamps(),
        sa.UniqueConstraint('board_id', 'position'),
    )
    op.create_index('ix_board_steps_board_id', 'board_steps', ['board_id'])
    op.create_table(
        'board_members',
        sa.Column('board_id', sa.Integer(), sa.ForeignKey('order_boards.id', ondelete='CASCADE'), nullable=False),
        sa.Column('step_id', sa.Integer(), sa.ForeignKey('board_steps.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        *_stamps(),
        sa.UniqueConstraint('step_id', 'user_id'),
    )
    op.create_index('ix_board_members_board_id', 'board_members', ['board_id'])
    op.create_index('ix_board_members_user_id', 'board_members', ['user_id'])


def downgrade() -> None:
    op.drop_table('board_members')
    op.drop_table('board_steps')
    op.drop_column('order_boards', 'created_by')
    op.drop_column('order_boards', 'notes')
