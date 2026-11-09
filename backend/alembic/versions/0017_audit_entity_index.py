"""audit log: an index for "everything that happened to one thing" (a board's History tab)

audit_log keeps every change in the company and is never trimmed, so looking up one board's lines
must not read the whole table. Only adds an index: no data changes.

Revision ID: 0017
Revises: 0016
"""
from typing import Sequence, Union

from alembic import op

revision: str = '0017'
down_revision: Union[str, None] = '0016'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_audit_log_entity', 'audit_log', ['entity_type', 'entity_id', 'id'])


def downgrade() -> None:
    op.drop_index('ix_audit_log_entity', table_name='audit_log')
