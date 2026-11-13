from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)  # stored lower-case
    phone: Mapped[str | None] = mapped_column(String(20))
    # Old password logins only (before Firebase, 13 Nov 2026). New accounts: None; Firebase keeps passwords.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    # The Firebase Authentication account this person signs in with (None = an old account, not linked yet)
    firebase_uid: Mapped[str | None] = mapped_column(String(128), unique=True)
    role: Mapped[str] = mapped_column(String(20), default="employee")  # admin | employee
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | active | disabled
    # Extra permission keys for this person (see app/core/permissions.py). Admins have all.
    permissions: Mapped[list[str]] = mapped_column(JSONB, default=list)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    # Product categories this person works on (auto-assign gives records only from these)
    categories: Mapped[list[str]] = mapped_column(JSONB, default=list)
    notify_email: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_whatsapp: Mapped[bool] = mapped_column(Boolean, default=False)  # opt-in (after Meta verification)
    joined_on: Mapped[date | None] = mapped_column(Date, default=date.today)
    shift_id: Mapped[int | None] = mapped_column(ForeignKey("shifts.id", ondelete="SET NULL"), nullable=True)
    # Set by the admin (User Creation Form). Staff see them on their profile but can't change them.
    employee_code: Mapped[str] = mapped_column(String(40), default="")
    branch: Mapped[str] = mapped_column(String(80), default="")
    reporting_to: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserSession(Base):
    """A logged-in browser. The cookie holds a random token; we store only its hash."""

    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AvailabilityLog(Base, TimestampMixin):
    __tablename__ = "availability_log"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    value: Mapped[bool] = mapped_column(Boolean)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
