"""KJS Chat. Any logged-in staff member; every route checks that you are in the chat (else 404).
Rules live in app/services/chat_service.py."""
import asyncio
import logging
import time
from typing import Literal

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import current_user, origin_allowed, ws_user
from app.models.user import User
from app.services import chat_hub, chat_service

log = logging.getLogger(__name__)
router = APIRouter()


class ChannelIn(BaseModel):
    kind: Literal["channel", "group"] = "channel"  # DMs are opened with POST /chat/dm/{user_id}
    name: str = Field(default="", max_length=80)
    description: str = Field(default="", max_length=500)
    is_private: bool = False
    member_ids: list[int] = Field(default_factory=list, max_length=200)


class ChannelPatch(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    archived: bool | None = None


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)  # plain text; the page never shows it as HTML
    mention_ids: list[int] = Field(default_factory=list, max_length=50)


class ReadIn(BaseModel):
    message_id: int | None = None  # empty = everything up to the newest


class MembersIn(BaseModel):
    user_ids: list[int] = Field(min_length=1, max_length=200)


@router.get("/channels")
async def my_channels(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await chat_service.my_channels(db, user)


@router.post("/channels", status_code=201)
async def create_channel(data: ChannelIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await chat_service.create_channel(db, user, kind=data.kind, name=data.name, description=data.description,
                                             is_private=data.is_private, member_ids=data.member_ids)


@router.get("/channels/{channel_id}")
async def get_channel(channel_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await chat_service.get_channel(db, user, channel_id)


@router.patch("/channels/{channel_id}")
async def update_channel(channel_id: int, data: ChannelPatch, user: User = Depends(current_user),
                         db: AsyncSession = Depends(get_db)):
    # Leaving a field out = don't change it; null counts as left out.
    changes = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    return await chat_service.update_channel(db, user, channel_id, changes)


@router.post("/dm/{user_id}")
async def open_dm(user_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await chat_service.open_dm(db, user, user_id)


@router.post("/channels/{channel_id}/members")
async def add_members(channel_id: int, data: MembersIn, user: User = Depends(current_user),
                      db: AsyncSession = Depends(get_db)):
    return await chat_service.add_members(db, user, channel_id, data.user_ids)


@router.delete("/channels/{channel_id}/members/{user_id}", status_code=204)
async def remove_member(channel_id: int, user_id: int, user: User = Depends(current_user),
                        db: AsyncSession = Depends(get_db)):
    """Remove someone (owner only), or leave the chat (user_id = your own id)."""
    await chat_service.remove_member(db, user, channel_id, user_id)


# ---------- Messages ----------
@router.get("/unread")
async def unread_total(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """The number on the sidebar's Chat entry (muted chats don't count)."""
    return {"total": await chat_service.unread_total(db, user)}


@router.get("/channels/{channel_id}/messages")
async def list_messages(channel_id: int, before: int | None = None, after: int | None = None,
                        limit: int = Query(default=50, ge=1, le=chat_service.PAGE_MAX),
                        user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await chat_service.list_messages(db, user, channel_id, before=before, after=after, limit=limit)


@router.post("/channels/{channel_id}/messages", status_code=201)
async def send_message(channel_id: int, data: MessageIn, user: User = Depends(current_user),
                       db: AsyncSession = Depends(get_db)):
    return await chat_service.send_message(db, user, channel_id, data.body, data.mention_ids)


@router.patch("/messages/{message_id}")
async def edit_message(message_id: int, data: MessageIn, user: User = Depends(current_user),
                       db: AsyncSession = Depends(get_db)):
    return await chat_service.edit_message(db, user, message_id, data.body, data.mention_ids)


@router.delete("/messages/{message_id}", status_code=204)
async def delete_message(message_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await chat_service.delete_message(db, user, message_id)


@router.post("/channels/{channel_id}/read", status_code=204)
async def mark_read(channel_id: int, data: ReadIn | None = None, user: User = Depends(current_user),
                    db: AsyncSession = Depends(get_db)):
    await chat_service.mark_read(db, user, channel_id, data.message_id if data else None)


# ---------- Live push (day 3) ----------
@router.websocket("/ws")
async def chat_socket(websocket: WebSocket):
    """One per open tab. Only pushes events (see chat_hub.py); sending uses the normal POST routes.
    1. Wrong Origin (another website): refused before it opens (the browser sees 403).
    2. Not logged in: opened, then closed with 4401 so the page knows to log in, not reconnect.
    3. Every PING_SECONDS, by the clock: check the session again (logout, expiry, disabled), then send
       a ping. By the clock, not "after PING_SECONDS of silence": otherwise a client that keeps sending
       something would never be re-checked and would keep getting messages after logout (PR #55 review).
    4. The browser has nothing to send (sending uses POST). More than MAX_FRAMES frames between two
       checks = something is wrong: closed. NOTE for phase 3 ("typing…"): the page will then send
       frames, so raise MAX_FRAMES (or count only unknown frames) when building it."""
    if not origin_allowed(websocket.headers.get("origin")):
        await websocket.close(code=1008)
        return
    token = websocket.cookies.get(settings.SESSION_COOKIE_NAME)
    user_id = await ws_user(token)
    await websocket.accept()
    if user_id is None:
        await websocket.close(code=chat_hub.CLOSE_LOGGED_OUT)
        return

    chat_hub.hub.add(user_id, websocket)
    try:
        await websocket.send_json({"type": "hello", "user_id": user_id})
        next_check = time.monotonic() + chat_hub.PING_SECONDS
        frames = 0  # sent by the browser since the last check
        while True:
            left = next_check - time.monotonic()
            if left <= 0:
                if await ws_user(token) != user_id:
                    await websocket.close(code=chat_hub.CLOSE_LOGGED_OUT)
                    return
                await websocket.send_json({"type": "ping"})
                next_check = time.monotonic() + chat_hub.PING_SECONDS
                frames = 0
                continue
            try:
                # This only notices when the browser goes away. receive(), not receive_text(): anything
                # the browser sends (text or binary) is ignored.
                msg = await asyncio.wait_for(websocket.receive(), timeout=left)
            except asyncio.TimeoutError:
                continue  # time for the check (top of the loop)
            if msg["type"] == "websocket.disconnect":
                return
            frames += 1
            if frames > chat_hub.MAX_FRAMES:
                log.warning("chat.socket_flood", extra={"user": user_id})
                await websocket.close(code=1008)  # policy violation
                return
    except WebSocketDisconnect:
        pass
    except RuntimeError as e:
        # The hub already closed it (kick, or a failed push) while this loop was waiting: nothing to do.
        log.info("chat.socket_already_closed", extra={"user": user_id, "error": str(e)[:120]})
    finally:
        chat_hub.hub.remove(user_id, websocket)
