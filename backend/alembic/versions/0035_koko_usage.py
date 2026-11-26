"""Koko's AI calls per day in the database (koko_usage), so the daily budget survives restarts (R72)

Only adds a table. The app user gets its rights from deploy/db/grants.sql (default privileges).

Revision ID: 0035
Revises: 0034
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0035'
down_revision: Union[str, None] = '0034'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'koko_usage',
        sa.Column('day', sa.Date(), primary_key=True),
        sa.Column('calls', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_table('koko_usage')
