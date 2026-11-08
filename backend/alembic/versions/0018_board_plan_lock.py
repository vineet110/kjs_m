"""order boards: the owner can lock the plan

order_boards.plan_locked: while true, only the owner (or boards.manage) may change the plan (dates,
step sizes, adding, renaming, removing and reordering steps). Existing boards start unlocked.

Only adds a column with a default: no data can be lost.

Revision ID: 0018
Revises: 0017
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0018'
down_revision: Union[str, None] = '0017'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('order_boards', sa.Column('plan_locked', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    op.drop_column('order_boards', 'plan_locked')
