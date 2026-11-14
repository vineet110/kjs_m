"""Monitoring (migration 0028): screenshots, screen-sharing on/off, breaks and idle periods.

Nothing here is written unless the person is checked in (monitor_service checks it).
"""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Screenshot(Base):
    """One screenshot. The image is in file storage under `screenshots/` (never served by /files)."""

    __tablename__ = "screenshots"
    __table_args__ = (Index("ix_screenshots_user_taken", "user_id", "taken_at"),
                      Index("ix_screenshots_taken", "taken_at"))  # the clean-up job

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    storage_key: Mapped[str] = mapped_column(String(200), unique=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(10), default="portal")  # portal | extension


class ShareEvent(Base):
    """Screen sharing started, stopped or refused. A `stopped` that isn't followed by `started` within
    gap_alert_minutes (while checked in) alerts admins once (alerted_at)."""

    __tablename__ = "share_events"
    __table_args__ = (Index("ix_share_events_user_at", "user_id", "at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    state: Mapped[str] = mapped_column(String(10))  # started | stopped | refused
    source: Mapped[str] = mapped_column(String(10), default="portal")  # portal | extension
    alerted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Break(Base):
    """A break (lunch, tea): tracking pauses. ended_at empty = on a break now."""

    __tablename__ = "breaks"
    __table_args__ = (Index("ix_breaks_user_day", "user_id", "day"),
                      Index("uq_breaks_one_open", "user_id", unique=True, postgresql_where=text("ended_at IS NULL")))

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    day: Mapped[date] = mapped_column(Date)  # IST day
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IdlePeriod(Base):
    """No keyboard or mouse for at least idle_warn_minutes (reported by the browser extension).
    ended_at empty = still idle. warned_at / admin_alerted_at: each sent once per period."""

    __tablename__ = "idle_periods"
    __table_args__ = (Index("ix_idle_periods_user_started", "user_id", "started_at"),
                      Index("uq_idle_periods_one_open", "user_id", unique=True,
                            postgresql_where=text("ended_at IS NULL")))

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(20), default="", server_default="")  # call | meeting | other
    reason_note: Mapped[str] = mapped_column(String(200), default="", server_default="")
    warned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    admin_alerted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
