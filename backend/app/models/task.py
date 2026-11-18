from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Task(Base, TimestampMixin):
    """One to-do for one person. Comes from: own (I added it), manager (someone gave it to me),
    lead, board (order-board step template) or batch (auto-assign)."""

    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_assignee_completed", "assignee_id", "completed_at"),)  # timeline (0027)

    title: Mapped[str] = mapped_column(String(200))
    notes: Mapped[str] = mapped_column(Text, default="")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(20), default="todo", index=True)  # todo | doing | done
    outcome: Mapped[str] = mapped_column(String(200), default="")
    source: Mapped[str] = mapped_column(String(20), default="own")  # own | manager | lead | board | batch
    source_ref: Mapped[str] = mapped_column(String(60), default="")  # e.g. "lead:12", "board:ABC117-3:step:2"
    assignee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
