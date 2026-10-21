from sqlalchemy import String, Boolean, ForeignKey, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin

class User(Base, TimestampMixin):
    __tablename__ = "users"
    
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="employee")  # admin, employee
    status: Mapped[str] = mapped_column(String(20), default="pending") # pending, active, disabled
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    shift_id: Mapped[int] = mapped_column(Integer, nullable=True)

class AvailabilityLog(Base, TimestampMixin):
    __tablename__ = "availability_log"
    
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    value: Mapped[bool] = mapped_column(Boolean)
    changed_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
