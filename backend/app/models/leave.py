from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class LeaveRequest(Base, TimestampMixin):
    """Leave requests submitted by employees and approved by managers/admins."""

    __tablename__ = "leave_requests"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    leave_type: Mapped[str] = mapped_column(String(30))  # casual | sick | earned | unpaid
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date] = mapped_column(Date, index=True)
    is_half_day: Mapped[bool] = mapped_column(Boolean, default=False)
    half_day_session: Mapped[str | None] = mapped_column(String(20))  # first_half | second_half
    reason: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending | approved | rejected | cancelled
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(String(255))

