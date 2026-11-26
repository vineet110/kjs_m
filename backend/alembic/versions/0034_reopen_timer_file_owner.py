"""Leads: reopened_at (a reopened lead's resolve timer counts from the reopen, CR12 / R4);
files: owner_id 60 -> 120 characters (a product slug can be 110, CR19)

Only adds a nullable column and widens one: the old code keeps working with the new schema.

Number 0034 follows 0033 on main. The open monitoring PRs (#83-#85) hold 0027-0029 with older
down_revisions: when they merge, renumber them after the newest head on main (else two heads, and
`alembic upgrade head` fails).

Revision ID: 0034
Revises: 0033
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0034'
down_revision: Union[str, None] = '0033'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('leads', sa.Column('reopened_at', sa.DateTime(timezone=True), nullable=True))
    op.alter_column('files', 'owner_id', type_=sa.String(120), existing_type=sa.String(60), existing_nullable=False)


def downgrade() -> None:
    # Only safe while no owner_id is longer than 60 (Postgres refuses the change otherwise: nothing is cut)
    op.alter_column('files', 'owner_id', type_=sa.String(60), existing_type=sa.String(120), existing_nullable=False)
    op.drop_column('leads', 'reopened_at')
