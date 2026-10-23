from datetime import date

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Holiday(Base, TimestampMixin):
    """Company holidays. Working days = Mon–Sat minus these (used by attendance,
    auto-assign, deadlines and order-board maths)."""

    __tablename__ = "holidays"

    day: Mapped[date] = mapped_column(Date, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
