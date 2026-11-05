from datetime import time

from sqlalchemy import Boolean, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Shift(Base, TimestampMixin):
    """Company work shifts (e.g. General, Morning, Night)."""

    __tablename__ = "shifts"

    name: Mapped[str] = mapped_column(String(50))
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    is_night_shift: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

