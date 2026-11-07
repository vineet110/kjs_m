"""order boards: people on a board, and step heads

- board_people: everyone on a board (can see and update it). The owner (order_boards.created_by)
  adds and removes people. Filled from the existing step members and owners, so nobody loses access.
- board_members.is_head: the head of a step (an assignee with a star). Existing rows become false.

Only adds things: no table or column is dropped or renamed, so no data can be lost.

Revision ID: 0016
Revises: 0015
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0016'
down_revision: Union[str, None] = '0015'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'board_people',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('board_id', sa.Integer(), sa.ForeignKey('order_boards.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('added_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('board_id', 'user_id', name='uq_board_people_board_user'),
    )
    op.create_index('ix_board_people_board_id', 'board_people', ['board_id'])
    op.create_index('ix_board_people_user_id', 'board_people', ['user_id'])

    # Everyone who can open a board today keeps that access: its step members and its owner.
    op.execute("""
        INSERT INTO board_people (board_id, user_id)
        SELECT DISTINCT board_id, user_id FROM board_members
        UNION
        SELECT id, created_by FROM order_boards WHERE created_by IS NOT NULL
        ON CONFLICT (board_id, user_id) DO NOTHING
    """)

    op.add_column('board_members', sa.Column('is_head', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    # Undo only what upgrade added. Step members (board_members) are untouched either way.
    op.drop_column('board_members', 'is_head')
    op.drop_index('ix_board_people_user_id', table_name='board_people')
    op.drop_index('ix_board_people_board_id', table_name='board_people')
    op.drop_table('board_people')
