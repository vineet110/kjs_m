"""Browser extension (migration 0029): connected computers, one-time connect codes, site visits and the
hourly site blocks people write an outcome for.

Keys and codes are stored only as SHA-256 hashes: a database leak never leaks a working key.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ExtensionDevice(Base):
    """One computer's extension. disabled_at set = its key is refused (switched off by the person or an admin)."""

    __tablename__ = "extension_devices"
    __table_args__ = (Index("ix_extension_devices_user", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80), default="")  # "Chrome on Windows", from the extension
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disabled_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class ExtensionPairCode(Base):
    """A one-time code shown on My activity ("Connect extension"), typed into the extension. Short-lived."""

    __tablename__ = "extension_pair_codes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SiteVisit(Base):
    """Time on one site in one tab, as the extension saw it (already cut to checked-in time by the server).
    (device_id, client_id) is unique: the same batch sent twice is saved once."""

    __tablename__ = "site_visits"
    __table_args__ = (UniqueConstraint("device_id", "client_id", name="uq_site_visits_device_client"),
                      Index("ix_site_visits_user_started", "user_id", "started_at"))

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    device_id: Mapped[int] = mapped_column(ForeignKey("extension_devices.id", ondelete="CASCADE"))
    client_id: Mapped[str] = mapped_column(String(64))
    domain: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(2000), default="")  # without ?query and #fragment unless store_query
    title: Mapped[str] = mapped_column(String(300), default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    seconds: Mapped[int] = mapped_column(Integer)


class SiteBlock(Base):
    """All time on one site in one IST hour: what the outcome is asked for (blocks of outcome_min_minutes+)."""

    __tablename__ = "site_blocks"
    __table_args__ = (UniqueConstraint("user_id", "domain", "hour_start", name="uq_site_blocks_user_domain_hour"),
                      Index("ix_site_blocks_user_hour", "user_id", "hour_start"))

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    domain: Mapped[str] = mapped_column(String(255))
    hour_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # the IST hour, stored in UTC
    seconds: Mapped[int] = mapped_column(Integer, default=0)
    outcome: Mapped[str] = mapped_column(Text, default="", server_default="")
    outcome_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
