"""Website showcase: brand_partners (logos in the sliding strip) and activity_lines (pop-up activity)

With no rows the website keeps its built-in partner names and shows no pop-ups, so this only adds tables:
existing rows and the old code keep working.

Number 0033: 0027-0029 are taken by the open monitoring PRs (#83-#85). Whichever of those merges after this
one points its down_revision at the newest number on main.

Revision ID: 0033
Revises: 0032
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0033'
down_revision: Union[str, None] = '0032'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _stamps() -> list[sa.Column]:
    return [
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        'brand_partners',
        *_stamps(),
        sa.Column('name', sa.String(60), nullable=False),
        sa.Column('logo_file_id', sa.Integer(), sa.ForeignKey('files.id'), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
    )
    op.create_table(
        'activity_lines',
        *_stamps(),
        sa.Column('text', sa.String(120), nullable=False),
        sa.Column('happened_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('activity_lines')
    op.drop_table('brand_partners')
