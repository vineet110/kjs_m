"""production readiness: one pending regularization per day, track removed stored files

Revision ID: 0011
Revises: 0010
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0011'
down_revision: Union[str, None] = '0010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Two quick clicks used to create two pending requests for the same day; approving both let the
    # second overwrite the first. Older duplicates (if any) keep only the newest pending one.
    op.execute("""
        UPDATE regularizations r SET status = 'rejected'
        WHERE status = 'pending' AND EXISTS (
            SELECT 1 FROM regularizations n
            WHERE n.user_id = r.user_id AND n.day = r.day AND n.status = 'pending' AND n.id > r.id)
    """)
    op.create_index('uq_regularizations_one_pending', 'regularizations', ['user_id', 'day'], unique=True,
                    postgresql_where=sa.text("status = 'pending'"))

    # A deleted file's stored copy is removed by a cleanup job if removing it right away failed.
    # Files deleted before this migration were already removed from storage.
    op.add_column('files', sa.Column('purged_at', sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE files SET purged_at = deleted_at WHERE deleted_at IS NOT NULL")


def downgrade() -> None:
    op.drop_column('files', 'purged_at')
    op.drop_index('uq_regularizations_one_pending', table_name='regularizations')
