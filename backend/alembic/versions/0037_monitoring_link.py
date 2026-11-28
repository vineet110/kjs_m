"""Monitoring link: attendance_events (the feed the monitoring server polls) and monitoring_link_state

Backfill: anyone whose last punch in the past 24 hours is a check-in gets one punch_in event, so a person
already at work when this ships shows as working on the monitoring side.

Number 0037 follows 0036 on main. 0027-0029 are still held by the parked monitoring PRs (#83-#85); this one
does not depend on them.

Revision ID: 0037
Revises: 0036
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0037'
down_revision: Union[str, None] = '0036'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attendance_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event", sa.String(12), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("ref", sa.String(60), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("clock_timestamp()")),  # the insert's moment, not the transaction's start
    )
    op.create_index("ix_attendance_events_created", "attendance_events", ["created_at", "id"])
    op.create_index("ix_attendance_events_user_at", "attendance_events", ["user_id", "at"])
    op.create_table(
        "monitoring_link_state",
        sa.Column("key", sa.String(40), primary_key=True),
        sa.Column("value", sa.String(200), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    # Each person's latest punch; only open check-ins of the past 24 hours (older ones are forgotten
    # check-outs: sending them would start monitoring for someone who isn't working)
    op.execute("""
        INSERT INTO attendance_events (user_id, event, at, source, ref)
        SELECT p.user_id, 'punch_in', p.punched_at, 'backfill', 'punch:' || p.id
        FROM (SELECT DISTINCT ON (user_id) id, user_id, punch_type, punched_at
              FROM attendance_punches ORDER BY user_id, punched_at DESC, id DESC) p
        WHERE p.punch_type = 'in' AND p.punched_at > now() - interval '24 hours'
    """)


def downgrade() -> None:
    op.drop_table("monitoring_link_state")
    op.drop_index("ix_attendance_events_user_at", table_name="attendance_events")
    op.drop_index("ix_attendance_events_created", table_name="attendance_events")
    op.drop_table("attendance_events")
