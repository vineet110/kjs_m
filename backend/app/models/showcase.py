from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class BrandPartner(Base, TimestampMixin):
    """A brand we make for, shown with its logo in the home page's sliding strip (Admin > Website > Partner
    logos). With no active row the strip shows the built-in names (frontend lib/site.ts)."""

    __tablename__ = "brand_partners"

    name: Mapped[str] = mapped_column(String(60))
    logo_file_id: Mapped[int | None] = mapped_column(ForeignKey("files.id"))  # owner website/partners; none = name only
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class ActivityLine(Base, TimestampMixin):
    """A true, recent piece of activity shown as a pop-up on the website, e.g. "A brand in Dubai requested a
    sample" (Admin > Website > Pop-up activity). The website turns happened_at into "2 hours ago"."""

    __tablename__ = "activity_lines"

    text: Mapped[str] = mapped_column(String(120))
    happened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
