"""Home page hero: hero_slides and hero_stats, edited in Admin > Website > Hero

With no rows the home page keeps its built-in slides and live counts, so this only adds tables: existing
rows and the old code keep working.

Number 0032: 0027-0029 are taken by the open monitoring PRs (#83-#85). Whichever of those merges after this
one points its down_revision at the newest number on main.

Revision ID: 0032
Revises: 0031
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0032'
down_revision: Union[str, None] = '0031'
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
        'hero_slides',
        *_stamps(),
        sa.Column('eyebrow', sa.String(60), nullable=False, server_default=''),
        sa.Column('title', sa.String(80), nullable=False),
        sa.Column('text', sa.String(240), nullable=False, server_default=''),
        sa.Column('cta_text', sa.String(30), nullable=False, server_default=''),
        sa.Column('cta_link', sa.String(255), nullable=False, server_default=''),
        sa.Column('tone', sa.String(20), nullable=False, server_default='gold'),
        sa.Column('image_ids', postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
    )
    op.create_table(
        'hero_stats',
        *_stamps(),
        sa.Column('number', sa.String(12), nullable=False),
        sa.Column('label', sa.String(60), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('hero_stats')
    op.drop_table('hero_slides')
