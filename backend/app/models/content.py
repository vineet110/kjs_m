from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Offer(Base, TimestampMixin):
    """A line in the offers ticker on the home page, shown between starts_at and ends_at."""

    __tablename__ = "offers"

    text: Mapped[str] = mapped_column(String(200))
    link: Mapped[str] = mapped_column(String(255), default="")
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class SiteText(Base, TimestampMixin):
    """Editable website text and SEO (e.g. key "home.hero_title", "seo.home.description",
    "koko.facts"). The code has a default for every key; a row here overrides it."""

    __tablename__ = "site_texts"

    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class PartnerApplication(Base, TimestampMixin):
    """Agents, brokers, freight forwarders and distributors who want to refer buyers."""

    __tablename__ = "partner_applications"

    name: Mapped[str] = mapped_column(String(120))
    company: Mapped[str] = mapped_column(String(200), default="")
    partner_type: Mapped[str] = mapped_column(String(40))  # agent | broker | forwarder | distributor | other
    country: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(30), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="new")  # new | approved | rejected
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class KokoChat(Base, TimestampMixin):
    """One Koko conversation (for the transcripts page and to improve the facts). The visitor
    is anonymous: we keep a random chat id and a hashed IP, never the raw IP."""

    __tablename__ = "koko_chats"

    chat_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    page: Mapped[str] = mapped_column(String(255), default="")
    messages: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    suggested_enquiry: Mapped[bool] = mapped_column(Boolean, default=False)
    ip_hash: Mapped[str | None] = mapped_column(String(64))
