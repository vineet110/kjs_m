from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class StoredFile(Base, TimestampMixin):
    """A file in storage (local folder or Cloudflare R2). We keep only the key here.
    Deleting needs approval: delete_status goes none -> requested -> approved/rejected."""

    __tablename__ = "files"
    __table_args__ = (Index("ix_files_owner", "owner_type", "owner_id"),)

    key: Mapped[str] = mapped_column(String(300), unique=True)
    name: Mapped[str] = mapped_column(String(200))  # original file name
    content_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    owner_type: Mapped[str] = mapped_column(String(30))  # board | product
    owner_id: Mapped[str] = mapped_column(String(60))
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)  # product images on the website
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # When the stored file itself was removed. Empty + deleted_at set = a cleanup job still has to do it.
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delete_status: Mapped[str] = mapped_column(String(20), default="none", index=True)
    delete_reason: Mapped[str] = mapped_column(String(500), default="")
    delete_requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
