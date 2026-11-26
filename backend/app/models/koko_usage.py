"""Koko's AI calls per day, so the daily budget (config/koko.ini daily_limit) survives a restart or a deploy
(backlog R72). One row per India-time day."""
from datetime import date

from sqlalchemy import Date, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KokoUsage(Base):
    __tablename__ = "koko_usage"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    calls: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
