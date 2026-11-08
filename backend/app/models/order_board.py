from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, false
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class OrderBoard(Base, TimestampMixin):
    """One customer order moving through steps (e.g. sourcing -> blending -> packing -> dispatch)."""

    __tablename__ = "order_boards"

    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)  # e.g. ABC117-3
    name: Mapped[str] = mapped_column(String(255))
    client: Mapped[str] = mapped_column(String(255))
    priority: Mapped[str] = mapped_column(String(20), default="medium")  # low | medium | high
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    split_mode: Mapped[str] = mapped_column(String(20), default="percent")  # percent | days
    status: Mapped[str] = mapped_column(String(30), default="active")  # active | finished
    final_status: Mapped[str | None] = mapped_column(String(30))  # Delivered | Returned | Cancelled
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    # Locked: only the owner (or boards.manage) changes the plan. Unlocked: anyone on the board (0017).
    plan_locked: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())


class BoardStep(Base, TimestampMixin):
    """A step of a board. Planned dates are working days (Mon–Sat minus holidays)."""

    __tablename__ = "board_steps"
    __table_args__ = (UniqueConstraint("board_id", "position"),)

    board_id: Mapped[int] = mapped_column(ForeignKey("order_boards.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)  # 1, 2, 3…
    name: Mapped[str] = mapped_column(String(120))
    percent: Mapped[int | None] = mapped_column(Integer)  # share of the board's working days (percent mode)
    days: Mapped[int | None] = mapped_column(Integer)  # fixed working days (days mode)
    planned_start: Mapped[date] = mapped_column(Date)
    planned_end: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | active | done
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    task_templates: Mapped[list[str]] = mapped_column(JSONB, default=list)  # tasks created when the step starts
    checklist: Mapped[list[dict]] = mapped_column(JSONB, default=list)  # [{"text": "...", "done": false}]
    alerted_pct: Mapped[int] = mapped_column(Integer, default=0)  # highest alert threshold already sent


class BoardMember(Base, TimestampMixin):
    """An assignee of one step. Assignees (and the head) can mark their step done."""

    __tablename__ = "board_members"
    __table_args__ = (UniqueConstraint("step_id", "user_id"),)

    board_id: Mapped[int] = mapped_column(ForeignKey("order_boards.id", ondelete="CASCADE"), index=True)
    step_id: Mapped[int] = mapped_column(ForeignKey("board_steps.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    is_head: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())


class BoardPerson(Base, TimestampMixin):
    """Everyone on a board (migration 0016): they can see it and update it (checklists, files).
    The owner (OrderBoard.created_by) and boards.manage add and remove people. Step assignees are
    always on the board too."""

    __tablename__ = "board_people"
    __table_args__ = (UniqueConstraint("board_id", "user_id", name="uq_board_people_board_user"),)

    board_id: Mapped[int] = mapped_column(ForeignKey("order_boards.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    added_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
