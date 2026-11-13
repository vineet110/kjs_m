from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Lead(Base, TimestampMixin):
    """Every enquiry from the website or Koko. We keep all of them (B2B buyers, retailers,
    distributors, private-label brands)."""

    __tablename__ = "leads"
    __table_args__ = (Index("ix_leads_assigned_to", "assigned_to"), Index("ix_leads_created_at", "created_at"))

    source: Mapped[str] = mapped_column(String(30))  # enquiry_form | price_sheet | koko | internal (typed in by staff)
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
    # SLA (config/sla.ini): respond = first "contacted", resolve = "closed"
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str] = mapped_column(String(40), default="")  # quote_sent, not_interested, …
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)  # 1 = respond late reported, 2 = resolve late reported
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))  # internal leads only; website/Koko = empty
    # "Extra Info": columns from an imported Excel / CSV file with no field of their own, kept because the
    # person chose "Add" ({"GST No": "36AB..."}). Migration 0022.
    extra: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class LeadNote(Base, TimestampMixin):
    """What staff did on a lead: a note, a call, an email, a hand-over."""

    __tablename__ = "lead_notes"

    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(20))  # note | call | email | handover | outcome
    text: Mapped[str] = mapped_column(Text, default="")
