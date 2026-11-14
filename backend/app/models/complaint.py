from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Complaint(Base, TimestampMixin):
    """A bug, issue or suggestion a staff member reported from the portal ("Report a problem").
    created_at = when it was filed. Screenshots are files with owner_type "complaint" (file_service)."""

    __tablename__ = "complaints"

    kind: Mapped[str] = mapped_column(String(20))  # bug | issue | suggestion
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    page_path: Mapped[str] = mapped_column(String(300))  # the portal page it was filed from
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
