"""Staff login through Firebase Authentication

users.firebase_uid: the Firebase account each person signs in with (unique). Empty for accounts made before
this change: they are linked the first time that person logs in with Firebase using the same, verified email.
users.password_hash: no longer required (Firebase keeps new passwords). Old hashes stay for now; dropped later.

Revision ID: 0021
Revises: 0020
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0021'
down_revision: Union[str, None] = '0020'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('firebase_uid', sa.String(128), nullable=True))
    op.create_unique_constraint('uq_users_firebase_uid', 'users', ['firebase_uid'])
    op.alter_column('users', 'password_hash', existing_type=sa.String(255), nullable=True)


def downgrade() -> None:
    # Accounts made through Firebase have no password hash: give them one nobody can log in with
    op.execute("UPDATE users SET password_hash = 'firebase-only' WHERE password_hash IS NULL")
    op.alter_column('users', 'password_hash', existing_type=sa.String(255), nullable=False)
    op.drop_constraint('uq_users_firebase_uid', 'users', type_='unique')
    op.drop_column('users', 'firebase_uid')
