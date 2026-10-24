"""auto-assign: record lists, buyer records, batches, employee categories

Revision ID: 0008
Revises: 0007
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0008'
down_revision: Union[str, None] = '0007'
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
    op.add_column('users', sa.Column('categories', postgresql.JSONB(), nullable=False, server_default='[]'))
    op.create_table(
        'record_lists',
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('rows', sa.Integer(), nullable=False),
        sa.Column('uploaded_by', sa.Integer(), sa.ForeignKey('users.id')),
        *_stamps(),
    )
    op.create_table(
        'batches',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('size', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        *_stamps(),
    )
    op.create_index('ix_batches_user_id', 'batches', ['user_id'])
    op.create_index('ix_batches_day', 'batches', ['day'])
    op.create_table(
        'buyer_records',
        sa.Column('list_id', sa.Integer(), sa.ForeignKey('record_lists.id', ondelete='CASCADE'), nullable=False),
        sa.Column('category', sa.String(60), nullable=False),
        sa.Column('company', sa.String(200), nullable=False),
        sa.Column('contact_name', sa.String(120), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('phone', sa.String(40), nullable=False),
        sa.Column('country', sa.String(80), nullable=False),
        sa.Column('website', sa.String(255), nullable=False),
        sa.Column('notes', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('batch_id', sa.Integer(), sa.ForeignKey('batches.id')),
        sa.Column('outcome', sa.String(300), nullable=False),
        sa.Column('done_at', sa.DateTime(timezone=True)),
        *_stamps(),
    )
    for col in ('list_id', 'category', 'status', 'batch_id'):
        op.create_index(f'ix_buyer_records_{col}', 'buyer_records', [col])


def downgrade() -> None:
    op.drop_table('buyer_records')
    op.drop_table('batches')
    op.drop_table('record_lists')
    op.drop_column('users', 'categories')
