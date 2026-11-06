from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Attendance(Base, TimestampMixin):
    """One row per person per working day (IST date). Times stored in UTC."""

    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("user_id", "day"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    check_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_seconds: Mapped[int] = mapped_column(Integer, server_default="0", default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="present")  # present | late | leave | half_day
    source: Mapped[str] = mapped_column(String(20), default="punch")  # punch | regularized

    punches: Mapped[list["AttendancePunch"]] = relationship(
        "AttendancePunch",
        back_populates="attendance",
        cascade="all, delete-orphan",
        order_by="AttendancePunch.punched_at",
        lazy="selectin",
    )


class AttendancePunch(Base, TimestampMixin):
    """A single check-in or check-out event during a work shift."""

    __tablename__ = "attendance_punches"

    id: Mapped[int] = mapped_column(primary_key=True)
    attendance_id: Mapped[int] = mapped_column(ForeignKey("attendance.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)
    punch_type: Mapped[str] = mapped_column(String(10))  # 'in' | 'out'
    punched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)

    attendance: Mapped["Attendance"] = relationship("Attendance", back_populates="punches")


class Regularization(Base, TimestampMixin):
    """'I forgot to punch' request. An approver fixes the day's times."""

    __tablename__ = "regularizations"
    # One open request per person per day: a double click can't create two (migration 0011)
    __table_args__ = (Index("uq_regularizations_one_pending", "user_id", "day", unique=True,
                            postgresql_where=text("status = 'pending'")),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    day: Mapped[date] = mapped_column(Date)
    check_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending | approved | rejected
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
