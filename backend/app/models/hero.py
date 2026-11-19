from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class HeroSlide(Base, TimestampMixin):
    """One slide of the big banner on the home page (Admin > Website > Hero). With no active slide, the
    home page shows its built-in slides. Pictures are files (owner "website") listed by id."""

    __tablename__ = "hero_slides"

    eyebrow: Mapped[str] = mapped_column(String(60), default="")  # small label above the title
    title: Mapped[str] = mapped_column(String(80))
    text: Mapped[str] = mapped_column(String(240), default="")
    cta_text: Mapped[str] = mapped_column(String(30), default="")  # button text
    cta_link: Mapped[str] = mapped_column(String(255), default="")
    tone: Mapped[str] = mapped_column(String(20), default="gold")  # background colour, one of hero_service.TONES
    image_ids: Mapped[list[int]] = mapped_column(JSONB, default=list)  # up to 3 file ids, in order
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class HeroStat(Base, TimestampMixin):
    """A number in the stats box next to the banner, e.g. "24" + "items and pack sizes to choose from".
    With no active stat, the home page shows the live counts from the catalogue."""

    __tablename__ = "hero_stats"

    number: Mapped[str] = mapped_column(String(12))  # digits count up on the page; text like "0.9–3 g" shows as is
    label: Mapped[str] = mapped_column(String(60))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
