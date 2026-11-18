from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SiteEvent(Base):
    """One thing a website visitor did: opened a page, searched, or clicked a tracked button.

    Anonymous on purpose (DPDP): no IP, no name, no cookie. `visit_id` is a random id the browser makes per tab
    and forgets when the tab closes, so "visits" can be counted without knowing who anyone is.
    Deleted after site_insights.ini keep_days. Not a TimestampMixin table: rows are never updated."""

    __tablename__ = "site_events"
    __table_args__ = (Index("ix_site_events_kind_at", "kind", "at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    visit_id: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(10))  # page | search | click
    path: Mapped[str] = mapped_column(String(300))  # the website page, like /products/instant-coffee
    product_slug: Mapped[str | None] = mapped_column(String(200))  # set on a product page
    category_slug: Mapped[str | None] = mapped_column(String(100))  # set on a category page
    button: Mapped[str | None] = mapped_column(String(40))  # click: a name from site_insights.ini buttons
    query: Mapped[str | None] = mapped_column(String(100))  # search: the words, phone numbers and emails hidden
    results: Mapped[int | None] = mapped_column(Integer)  # search: how many products matched
    device: Mapped[str] = mapped_column(String(10))  # mobile | tablet | desktop (from the browser name)
    source: Mapped[str | None] = mapped_column(String(100))  # first page of a visit: the site it came from
