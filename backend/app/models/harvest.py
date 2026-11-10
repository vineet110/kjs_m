from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class HarvestSource(Base, TimestampMixin):
    """An external source of buyer enquiries (API, Open Data file, RSS feed, or Web Scrape)."""

    __tablename__ = "harvest_sources"
    __table_args__ = (
        Index("ix_harvest_sources_source_type", "source_type"),
        Index("ix_harvest_sources_is_active", "is_active"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # api | open_data | rss | scrape
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    # Security: auth_env_var holds ONLY the name of the environment variable (e.g. INDIAMART_API_KEY).
    # Raw API keys or secrets are NEVER stored in the database.
    auth_env_var: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    category: Mapped[str] = mapped_column(String(60), default="all", nullable=False)  # all | coffee | tea | spices | private_label
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    terms_checked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # required for scrape sources
    schedule_interval_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str] = mapped_column(String(30), default="idle", nullable=False)  # idle | success | partial | failed | blocked_by_robots
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class HarvestRun(Base, TimestampMixin):
    """Audit log of an ingestion run for one source, tracking accepted and dropped counts with reasons."""

    __tablename__ = "harvest_runs"
    __table_args__ = (
        Index("ix_harvest_runs_source_id", "source_id"),
        Index("ix_harvest_runs_started_at", "started_at"),
    )

    source_id: Mapped[int] = mapped_column(ForeignKey("harvest_sources.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)  # success | partial | failed | blocked_by_robots
    found_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dropped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    drop_reasons: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)  # e.g. {"product_mismatch": 5, "invalid_contact": 2, "duplicate": 1}
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

