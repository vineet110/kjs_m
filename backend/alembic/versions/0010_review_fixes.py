"""review fixes: email retries, one open batch per person, indexes for growing tables

Revision ID: 0010
Revises: 0009
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0010'
down_revision: Union[str, None] = '0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Email copies are retried up to 3 times before "failed"
    op.add_column('notifications', sa.Column('email_attempts', sa.Integer(), server_default='0', nullable=False))

    # The database itself now refuses a second open batch for the same person
    # (two auto-assign runs at the same moment could otherwise both create one).
    op.create_index('uq_batches_one_open_per_user', 'batches', ['user_id'], unique=True,
                    postgresql_where=sa.text("status = 'open'"))

    # Lists sort by newest first; auto-assign picks new records per category
    op.create_index('ix_leads_created_at', 'leads', ['created_at'])
    op.create_index('ix_buyer_records_pick', 'buyer_records', ['status', 'category', 'id'])


def downgrade() -> None:
    op.drop_index('ix_buyer_records_pick', table_name='buyer_records')
    op.drop_index('ix_leads_created_at', table_name='leads')
    op.drop_index('uq_batches_one_open_per_user', table_name='batches')
    op.drop_column('notifications', 'email_attempts')
