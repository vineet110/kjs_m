"""Complaints: bugs, issues and suggestions staff report from the portal

complaints: one row per report (kind, title, description, the page it came from, who filed it).
created_at is the date and time it was filed. Screenshots live in `files` (owner_type "complaint").

Only adds a table: existing rows and the old code keep working.

Number 0026: open PR #77 (feat/firebase-auth) already uses 0024 and 0025. This one comes after 0023
(the newest on main today). Whichever merges second changes its down_revision to the other's last one.

Revision ID: 0026
Revises: 0023
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0026'
down_revision: Union[str, None] = '0023'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'complaints',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('kind', sa.String(20), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('page_path', sa.String(300), nullable=False),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_complaints_created_by', 'complaints', ['created_by'])


def downgrade() -> None:
    op.drop_index('ix_complaints_created_by', table_name='complaints')
    op.drop_table('complaints')
