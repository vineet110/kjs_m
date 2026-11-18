"""Website insights: site_events, one row per page view, search or tracked button click on the website

Anonymous: no IP, no name, no cookie (see app/models/site_event.py). Old rows are deleted after
config/site_insights.ini keep_days.

Only adds a table: existing rows and the old code keep working.

Number 0031: 0027-0029 are taken by the open monitoring PRs (#83-#85) and 0030 by hide_tea. Whichever of
those merges after this one points its down_revision at the newest number on main.

Revision ID: 0031
Revises: 0030
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0031'
down_revision: Union[str, None] = '0030'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'site_events',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('visit_id', sa.String(40), nullable=False),
        sa.Column('kind', sa.String(10), nullable=False),
        sa.Column('path', sa.String(300), nullable=False),
        sa.Column('product_slug', sa.String(200), nullable=True),
        sa.Column('category_slug', sa.String(100), nullable=True),
        sa.Column('button', sa.String(40), nullable=True),
        sa.Column('query', sa.String(100), nullable=True),
        sa.Column('results', sa.Integer(), nullable=True),
        sa.Column('device', sa.String(10), nullable=False),
        sa.Column('source', sa.String(100), nullable=True),
    )
    op.create_index('ix_site_events_at', 'site_events', ['at'])
    op.create_index('ix_site_events_kind_at', 'site_events', ['kind', 'at'])


def downgrade() -> None:
    op.drop_index('ix_site_events_kind_at', table_name='site_events')
    op.drop_index('ix_site_events_at', table_name='site_events')
    op.drop_table('site_events')
