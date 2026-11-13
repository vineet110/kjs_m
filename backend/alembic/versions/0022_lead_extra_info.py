"""Leads: "Extra Info" (columns from an imported Excel / CSV file that we have no field for)

leads.extra: {column name: value}, e.g. {"GST No": "36ABCDE1234F1Z5"}. Filled only when the person who
read the file chose "Add" for that column; rejected columns are never saved. Shown as "Extra Info".
Approved by Vineet on PR #74 (13 Nov).

Number 0022: two open branches already use 0021 (feat/firebase-auth, feat/employee-permissions). Whichever
merges first, point down_revision below at the newest migration on main before merging this one.

Adds one column with a default: existing leads get {} and nothing else changes.

Revision ID: 0022
Revises: 0020
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = '0022'
down_revision: Union[str, None] = '0020'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('leads', sa.Column('extra', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")))


def downgrade() -> None:
    op.drop_column('leads', 'extra')
