"""files

Revision ID: 0006
Revises: 0005
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'files',
        sa.Column('key', sa.String(300), nullable=False, unique=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('content_type', sa.String(100), nullable=False),
        sa.Column('size', sa.Integer(), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('owner_type', sa.String(30), nullable=False),
        sa.Column('owner_id', sa.String(60), nullable=False),
        sa.Column('is_public', sa.Boolean(), nullable=False),
        sa.Column('uploaded_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('deleted_at', sa.DateTime(timezone=True)),
        sa.Column('delete_status', sa.String(20), nullable=False),
        sa.Column('delete_reason', sa.String(500), nullable=False),
        sa.Column('delete_requested_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_files_owner', 'files', ['owner_type', 'owner_id'])
    op.create_index('ix_files_delete_status', 'files', ['delete_status'])


def downgrade() -> None:
    op.drop_table('files')
