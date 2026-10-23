from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class OrderBoard(Base, TimestampMixin):
    """Phase 5. Table exists now so later migrations only add to it."""

    __tablename__ = "order_boards"

    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)  # ^ABC117-[0-9]{1,6}$
    name: Mapped[str] = mapped_column(String(255))
    client: Mapped[str] = mapped_column(String(255))
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    split_mode: Mapped[str] = mapped_column(String(20), default="percent")  # percent | days
    status: Mapped[str] = mapped_column(String(30), default="active")
    final_status: Mapped[str | None] = mapped_column(String(30))  # Delivered | Returned | Cancelled
