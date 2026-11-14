"""A password reset ends every session at once (review of #77, step 2)

users.firebase_valid_after: when this person's Firebase password last changed (from Firebase). A session that
began before it has ended. users.firebase_checked_at: when we last asked Firebase (at most every 5 minutes).

Also: sessions of accounts not linked to Firebase yet (made before 13 Nov) are deleted. Those people log in
once more, which links them, and then their Profile password change works.

Revision ID: 0025
Revises: 0024
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0025'
down_revision: Union[str, None] = '0024'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('firebase_valid_after', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('firebase_checked_at', sa.DateTime(timezone=True), nullable=True))
    op.execute("DELETE FROM user_sessions WHERE user_id IN (SELECT id FROM users WHERE firebase_uid IS NULL)")


def downgrade() -> None:
    # The deleted sessions don't come back (those people just log in again)
    op.drop_column('users', 'firebase_checked_at')
    op.drop_column('users', 'firebase_valid_after')
