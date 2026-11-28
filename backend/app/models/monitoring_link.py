"""The link to the laptop-monitoring server (migration 0037).

The monitoring server polls our attendance feed (api/v1/endpoints/monitoring_link.py). It applies each
event id once and never edits history, so the events here are append-only and, per person, always
alternate punch_in -> punch_out -> punch_in (services/monitoring_link_service.py keeps that rule).
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AttendanceEvent(Base):
    """One start or stop of working time, as the monitoring server sees it."""

    __tablename__ = "attendance_events"
    __table_args__ = (Index("ix_attendance_events_created", "created_at", "id"),
                      Index("ix_attendance_events_user_at", "user_id", "at"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    event: Mapped[str] = mapped_column(String(12))  # punch_in | punch_out (break_start | break_end later)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # when it happened (UTC)
    source: Mapped[str] = mapped_column(String(20))  # punch | auto | regularization | backfill
    ref: Mapped[str] = mapped_column(String(60), default="", server_default="")  # e.g. reg:12, shift_end
    # When it was written: the feed's cursor. clock_timestamp() (the moment of the insert), not now() (the
    # transaction's start); a row still commits a moment later, so the feed reads back feed_overlap_seconds.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())


class MonitoringAlertSeen(Base):
    """A monitoring alert whose bell has rung (a push and the catch-up job may both bring the same one)."""

    __tablename__ = "monitoring_alerts_seen"

    alert_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MonitoringLinkState(Base):
    """Small values the link keeps between runs (e.g. the alerts cursor, Phase 3)."""

    __tablename__ = "monitoring_link_state"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[str] = mapped_column(String(200), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now())
