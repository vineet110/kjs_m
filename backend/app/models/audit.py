from sqlalchemy import String, Integer, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class AuditLog(Base):
    __tablename__ = "audit_log"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor_id: Mapped[str] = mapped_column(String(50)) # User ID or 'system'
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(50))
    before: Mapped[dict] = mapped_column(JSON, nullable=True)
    after: Mapped[dict] = mapped_column(JSON, nullable=True)
    ip: Mapped[str] = mapped_column(String(45), nullable=True)
