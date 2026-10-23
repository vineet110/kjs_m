from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    """Who changed what, and when. Append-only: a DB trigger blocks UPDATE and DELETE
    (see the first migration). Always written in the same transaction as the change."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))  # NULL = system / visitor
    actor_label: Mapped[str] = mapped_column(String(120))  # "Admin (vineet@…)", "system", "visitor"
    action: Mapped[str] = mapped_column(String(100))  # e.g. "user.approved"
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str | None] = mapped_column(String(50))
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    ip_hash: Mapped[str | None] = mapped_column(String(64))
