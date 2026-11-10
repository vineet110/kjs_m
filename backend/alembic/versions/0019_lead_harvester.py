"""lead harvester: harvest_sources and harvest_runs tables

- harvest_sources: external sources of buyer enquiries (API, Open Data, RSS, Scrape)
  with schedule, status, and auth_env_var (names only, secrets never stored in DB).
- harvest_runs: per-source execution history, metrics (found, accepted, dropped),
  and breakdown of drop reasons (DPDP compliance, product mismatch, duplicates, invalid contact).

Revision ID: 0019
Revises: 0018
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "harvest_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("auth_env_var", sa.String(length=100), server_default="", nullable=False),
        sa.Column("category", sa.String(length=60), server_default="all", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("terms_checked", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("schedule_interval_minutes", sa.Integer(), server_default="15", nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(length=30), server_default="idle", nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_harvest_sources_source_type", "harvest_sources", ["source_type"])
    op.create_index("ix_harvest_sources_is_active", "harvest_sources", ["is_active"])

    op.create_table(
        "harvest_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("harvest_sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("found_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("accepted_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("dropped_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("drop_reasons", JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("error_message", sa.Text(), server_default="", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_harvest_runs_source_id", "harvest_runs", ["source_id"])
    op.create_index("ix_harvest_runs_started_at", "harvest_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_harvest_runs_started_at", table_name="harvest_runs")
    op.drop_index("ix_harvest_runs_source_id", table_name="harvest_runs")
    op.drop_table("harvest_runs")

    op.drop_index("ix_harvest_sources_is_active", table_name="harvest_sources")
    op.drop_index("ix_harvest_sources_source_type", table_name="harvest_sources")
    op.drop_table("harvest_sources")

