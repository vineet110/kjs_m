from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class RecordList(Base, TimestampMixin):
    """One imported file of buyer records (Excel/CSV)."""

    __tablename__ = "record_lists"

    name: Mapped[str] = mapped_column(String(200))
    rows: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class BuyerRecord(Base, TimestampMixin):
    """One company/contact to work on (call, email, qualify). Auto-assign puts records into batches."""

    __tablename__ = "buyer_records"
    # Auto-assign picks "new records of this category, oldest first" (migration 0010)
    __table_args__ = (Index("ix_buyer_records_pick", "status", "category", "id"),)

    list_id: Mapped[int] = mapped_column(ForeignKey("record_lists.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(60), index=True)  # category slug, e.g. coffee
    company: Mapped[str] = mapped_column(String(200))
    contact_name: Mapped[str] = mapped_column(String(120), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(40), default="")
    country: Mapped[str] = mapped_column(String(80), default="")
    website: Mapped[str] = mapped_column(String(255), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)  # new | assigned | done | skipped
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("batches.id"), index=True)
    outcome: Mapped[str] = mapped_column(String(300), default="")
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Batch(Base, TimestampMixin):
    """A set of records given to one person on one day."""

    __tablename__ = "batches"
    __table_args__ = (Index("uq_batches_one_open_per_user", "user_id", unique=True,
                            postgresql_where=text("status = 'open'")),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    day: Mapped[date] = mapped_column(Date, index=True)  # IST date
    size: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | done
