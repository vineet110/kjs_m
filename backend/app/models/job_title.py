from sqlalchemy import ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class JobTitle(Base, TimestampMixin):
    """A job title admins pick from on the user form ("Sales Executive"). Unique whatever its case.
    A label only: access comes from permissions."""

    __tablename__ = "job_titles"
    __table_args__ = (Index("uq_job_titles_name_lower", func.lower("name"), unique=True),)

    name: Mapped[str] = mapped_column(String(60))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
