from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Lead(Base, TimestampMixin):
    """Every enquiry from the website or Koko. We keep all of them (B2B buyers, retailers,
    distributors, private-label brands)."""

    __tablename__ = "leads"

    source: Mapped[str] = mapped_column(String(30))  # enquiry_form | price_sheet | koko
    name: Mapped[str] = mapped_column(String(120))
    company: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(30), default="")
    country: Mapped[str] = mapped_column(String(80), default="")
    buyer_type: Mapped[str] = mapped_column(String(40), default="")  # distributor, retailer, brand…
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    quantity: Mapped[str] = mapped_column(String(120), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    chat_summary: Mapped[str] = mapped_column(Text, default="")  # Koko leads only
    source_page: Mapped[str] = mapped_column(String(255), default="")
    consent: Mapped[bool] = mapped_column(Boolean)
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)  # new | contacted | closed
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
