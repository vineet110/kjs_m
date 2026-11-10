"""KJS Chat (migration 0020): channels, group chats and DMs, their members and messages."""
from datetime import datetime

from sqlalchemy import (Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint, false, func)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ChatChannel(Base, TimestampMixin):
    """A channel (#sales), a group chat (a few people, name optional) or a DM (exactly 2 people)."""

    __tablename__ = "chat_channels"
    __table_args__ = (CheckConstraint("kind IN ('channel', 'group', 'dm')", name="ck_chat_channels_kind"),)

    kind: Mapped[str] = mapped_column(String(10))  # channel | group | dm
    name: Mapped[str] = mapped_column(String(80), default="", server_default="")
    description: Mapped[str] = mapped_column(String(500), default="", server_default="")
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # DMs only: "12:45" (smaller id first). Unique, so each pair has one DM. NULL for the other kinds.
    dm_key: Mapped[str | None] = mapped_column(String(30), unique=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # set = read-only


class ChatMember(Base, TimestampMixin):
    """One person in one channel. Each person is in a channel only once."""

    __tablename__ = "chat_members"
    __table_args__ = (UniqueConstraint("channel_id", "user_id", name="uq_chat_members_channel_user"),)

    channel_id: Mapped[int] = mapped_column(ForeignKey("chat_channels.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(10), default="member", server_default="member")  # owner | member
    # Everything after this message id is unread for this person (0 = nothing read yet).
    last_read_message_id: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    muted: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())


class ChatMessage(Base):
    """One message. Deleting only sets deleted_at (shown as "message deleted")."""

    __tablename__ = "chat_messages"
    __table_args__ = (Index("ix_chat_messages_channel_id_id", "channel_id", "id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("chat_channels.id", ondelete="CASCADE"))
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    mentions: Mapped[list[int]] = mapped_column(JSONB, default=list, server_default="[]")  # user ids
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("chat_messages.id"))  # replies (phase 2)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
