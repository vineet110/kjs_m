"""Laptop monitoring pages: monitoring_alerts_seen (which monitoring alerts already rang a bell)

A push and the catch-up job may both bring the same alert; this keeps it to one bell.

Revision ID: 0038
Revises: 0037
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0038'
down_revision: Union[str, None] = '0037'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "monitoring_alerts_seen",
        sa.Column("alert_id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("monitoring_alerts_seen")
