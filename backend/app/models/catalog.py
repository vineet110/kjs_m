from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Category(Base, TimestampMixin):
    __tablename__ = "categories"

    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Product(Base, TimestampMixin):
    """A product KJS makes. No price column yet: prices wait for KJS input (backlog I3 / D19)."""

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("offer_percent IS NULL OR offer_percent BETWEEN 1 AND 90", name="ck_products_offer_percent"),
    )

    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    pack_formats: Mapped[str] = mapped_column(String(255), default="")  # "Stick pack 18 g, Jar 200 g"
    moq: Mapped[str] = mapped_column(String(120), default="")  # minimum order, free text for now
    image_path: Mapped[str] = mapped_column(String(255), default="")  # file key, never the file itself
    private_label: Mapped[bool] = mapped_column(Boolean, default=True)
    is_best_seller: Mapped[bool] = mapped_column(Boolean, default=False)
    # "Up to X% OFF" badge on the website; empty = no offer (set by staff in Admin > Products)
    offer_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
