"""KJS Chat, phase 1: channels, group chats, DMs, their members (day 1) and messages (day 2).

Rules (docs/tempV.md, KJS Chat plan):
1. Every logged-in staff member can chat with anyone. No permission needed.
2. You only ever see channels you are a member of. For a non-member a channel doesn't exist: 404, not
   403, so nobody can find out which channel ids exist.
3. Channel: the owner renames, archives, adds and removes people. Anyone can leave.
4. Group chat (a few people, name optional): any member adds people or renames it; only the owner
   removes others or archives it. Anyone can leave.
5. DM: always exactly 2 people, one per pair (the unique dm_key). No renaming, adding or removing.
6. Archived = read-only: no renaming or member changes until the owner un-archives it.
7. When the last owner leaves, the longest-standing member becomes owner. When the last person
   leaves, the channel is archived.
8. Member removals, renames and archiving go in the audit log.
9. Messages: any member sends (not in archived chats). Only the sender edits or deletes their own;
   anyone else gets 404. Deleting empties the body and shows "message deleted".
10. Unread = messages from others, not deleted, after my last_read_message_id. Sending marks the
    chat read for me (my own message is never unread).
11. @mentions: the client sends the ids; we keep only members of the chat (not me) and give each one
    a normal notification (bell + email), also when they muted the chat.
12. Sending is rate-limited per person: 30 messages a minute.
13. After each save, the live hub pushes an event to the members who are online (day 3, chat_hub.py).
"""
from datetime import datetime, timezone

from sqlalchemy import and_, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.rate_limit import chat_send_limiter
from app.models.chat import ChatChannel, ChatMember, ChatMessage
from app.models.user import User
from app.services import audit_service, notification_service
from app.services.chat_hub import hub

PAGE_MAX = 100  # most messages one request may ask for


def dm_key(a: int, b: int) -> str:
    """The same key whoever opens the DM: smaller id first."""
    return f"{min(a, b)}:{max(a, b)}"


def _not_found() -> AppError:
    return AppError(404, "not_found", "Chat not found.")


async def _membership(db: AsyncSession, channel_id: int, user_id: int) -> tuple[ChatChannel, ChatMember]:
    """The channel and my row in it, or 404 (also when the channel doesn't exist at all)."""
    row = (await db.execute(
        select(ChatChannel, ChatMember)
        .join(ChatMember, ChatMember.channel_id == ChatChannel.id)
        .where(ChatChannel.id == channel_id, ChatMember.user_id == user_id)
    )).first()
    if row is None:
        raise _not_found()
    return row[0], row[1]


def _not_archived(ch: ChatChannel) -> None:
    if ch.archived_at is not None:
        raise AppError(409, "archived", "This chat is archived. It can be read but not changed.")


def _not_dm(ch: ChatChannel) -> None:
    if ch.kind == "dm":
        raise AppError(422, "not_for_dm", "A direct message always has exactly two people. Start a group chat instead.")


def _must_own(me: ChatMember) -> None:
    if me.role != "owner":
        raise AppError(403, "not_owner", "Only the chat's owner can do this.")


async def _active_users(db: AsyncSession, ids: list[int], *, exclude: int | None = None) -> list[int]:
    """Check every id is an active colleague. Removes duplicates and `exclude` (usually me)."""
    wanted = sorted({i for i in ids if i != exclude})
    if not wanted:
        return []
    found = set((await db.scalars(select(User.id).where(User.id.in_(wanted), User.status == "active"))).all())
    missing = [i for i in wanted if i not in found]
    if missing:
        raise AppError(422, "bad_user", "Pick active colleagues only.", {"user_ids": missing})
    return wanted


async def _members_of(db: AsyncSession, channel_ids: list[int]) -> dict[int, list[dict]]:
    """channel id -> [{id, name, role}], oldest member first."""
    out: dict[int, list[dict]] = {cid: [] for cid in channel_ids}
    if not channel_ids:
        return out
    rows = await db.execute(
        select(ChatMember.channel_id, User.id, User.name, ChatMember.role)
        .join(User, User.id == ChatMember.user_id)
        .where(ChatMember.channel_id.in_(channel_ids))
        .order_by(ChatMember.id)
    )
    for cid, uid, name, role in rows.all():
        out[cid].append({"id": uid, "name": name, "role": role})
    return out


async def _member_ids(db: AsyncSession, channel_id: int) -> list[int]:
    return list((await db.scalars(select(ChatMember.user_id).where(ChatMember.channel_id == channel_id))).all())


async def _push(db: AsyncSession, channel_id: int, event: dict, *, also: tuple[int, ...] = ()) -> None:
    """Live event to everyone in the chat (and `also`, e.g. someone just removed). Call after commit."""
    await hub.push([*await _member_ids(db, channel_id), *also], {"channel_id": channel_id} | event)


def _title(ch: ChatChannel, members: list[dict], my_id: int) -> str:
    """What the list shows: the name; for a DM the other person; for an unnamed group, the people."""
    others = [m["name"] for m in members if m["id"] != my_id]
    if ch.kind == "dm":
        return others[0] if others else "Direct message"
    if ch.name:
        return ch.name
    return ", ".join(others[:3]) + (f" +{len(others) - 3}" if len(others) > 3 else "")


def _out(ch: ChatChannel, me: ChatMember, members: list[dict], my_id: int) -> dict:
    other = next((m for m in members if m["id"] != my_id), None) if ch.kind == "dm" else None
    return {
        "id": ch.id, "kind": ch.kind, "title": _title(ch, members, my_id), "name": ch.name,
        "description": ch.description, "is_private": ch.is_private,
        "archived": ch.archived_at is not None, "my_role": me.role, "muted": me.muted,
        "member_count": len(members), "dm_user": {"id": other["id"], "name": other["name"]} if other else None,
        "created_at": ch.created_at,
    }


# ---------- Reading ----------

async def _unread(db: AsyncSession, user_id: int) -> dict[int, tuple[int, int]]:
    """channel id -> (my unread count, newest message id), for every chat I'm in. One query."""
    unread = func.count().filter(and_(ChatMessage.id > ChatMember.last_read_message_id,
                                      ChatMessage.deleted_at.is_(None),
                                      ChatMessage.sender_id != user_id))
    rows = await db.execute(
        select(ChatMessage.channel_id, unread, func.max(ChatMessage.id))
        .join(ChatMember, and_(ChatMember.channel_id == ChatMessage.channel_id, ChatMember.user_id == user_id))
        .group_by(ChatMessage.channel_id)
    )
    return {cid: (n, last) for cid, n, last in rows.all()}


async def my_channels(db: AsyncSession, user: User) -> list[dict]:
    """Channels first (A to Z), then group chats and DMs (latest message first). Archived at the end."""
    rows = (await db.execute(
        select(ChatChannel, ChatMember)
        .join(ChatMember, ChatMember.channel_id == ChatChannel.id)
        .where(ChatMember.user_id == user.id)
    )).all()
    members = await _members_of(db, [ch.id for ch, _ in rows])
    counts = await _unread(db, user.id)
    out = []
    for ch, me in rows:
        n, last = counts.get(ch.id, (0, 0))
        out.append(_out(ch, me, members[ch.id], user.id) | {"unread": n, "last_message_id": last})
    out.sort(key=lambda c: (c["archived"], c["kind"] != "channel",
                            c["title"].lower() if c["kind"] == "channel" else -c["last_message_id"]))
    return out


async def unread_total(db: AsyncSession, user: User) -> int:
    """For the sidebar badge. Muted chats don't count."""
    muted = set((await db.scalars(
        select(ChatMember.channel_id).where(ChatMember.user_id == user.id, ChatMember.muted.is_(True)))).all())
    return sum(n for cid, (n, _) in (await _unread(db, user.id)).items() if cid not in muted)


async def get_channel(db: AsyncSession, user: User, channel_id: int) -> dict:
    """One chat with its member list."""
    ch, me = await _membership(db, channel_id, user.id)
    members = (await _members_of(db, [ch.id]))[ch.id]
    return _out(ch, me, members, user.id) | {"members": members}


# ---------- Creating ----------

async def create_channel(db: AsyncSession, user: User, *, kind: str, name: str, description: str,
                         is_private: bool, member_ids: list[int]) -> dict:
    """A channel (needs a name) or a group chat (needs at least 2 other people). I become the owner."""
    name, description = name.strip(), description.strip()
    others = await _active_users(db, member_ids, exclude=user.id)
    if kind == "channel" and len(name) < 2:
        raise AppError(422, "name_required", "Give the channel a name (at least 2 characters).")
    if kind == "group" and len(others) < 2:
        raise AppError(422, "too_few_people", "A group chat needs at least 2 other people. For one person, open a direct message.")
    ch = ChatChannel(kind=kind, name=name, description=description,
                     is_private=is_private if kind == "channel" else True, created_by=user.id)
    db.add(ch)
    await db.flush()  # gives ch.id
    db.add(ChatMember(channel_id=ch.id, user_id=user.id, role="owner"))
    for uid in others:
        db.add(ChatMember(channel_id=ch.id, user_id=uid, role="member"))
    await db.commit()
    await _push(db, ch.id, {"type": "channel.changed"})
    return await get_channel(db, user, ch.id)


async def open_dm(db: AsyncSession, user: User, other_id: int) -> dict:
    """The DM between me and that person, created the first time. Safe on two clicks at once:
    the unique dm_key lets only one insert through ("ON CONFLICT DO NOTHING"), the other finds it."""
    if other_id == user.id:
        raise AppError(422, "dm_self", "You can't start a direct message with yourself.")
    await _active_users(db, [other_id])
    key = dm_key(user.id, other_id)
    new_id = await db.scalar(
        pg_insert(ChatChannel)
        .values(kind="dm", is_private=True, dm_key=key, created_by=user.id)
        .on_conflict_do_nothing(index_elements=["dm_key"])
        .returning(ChatChannel.id)
    )
    channel_id = new_id or await db.scalar(select(ChatChannel.id).where(ChatChannel.dm_key == key))
    await db.execute(
        pg_insert(ChatMember)
        .values([{"channel_id": channel_id, "user_id": uid, "role": "member"} for uid in (user.id, other_id)])
        .on_conflict_do_nothing(constraint="uq_chat_members_channel_user")
    )
    await db.commit()
    if new_id:
        await _push(db, channel_id, {"type": "channel.changed"})
    return await get_channel(db, user, channel_id)


# ---------- Changing ----------

async def update_channel(db: AsyncSession, user: User, channel_id: int, changes: dict) -> dict:
    """Rename, change the description, archive or un-archive. Archiving and un-archiving: owner only."""
    ch, me = await _membership(db, channel_id, user.id)
    _not_dm(ch)
    before = {"name": ch.name, "description": ch.description, "archived": ch.archived_at is not None}

    if "archived" in changes:
        _must_own(me)
        if changes["archived"] and ch.archived_at is None:
            ch.archived_at = datetime.now(timezone.utc)
        elif not changes["archived"]:
            ch.archived_at = None
    if "name" in changes or "description" in changes:
        _not_archived(ch)
        if ch.kind == "channel":
            _must_own(me)  # in a group chat any member may rename
        if "name" in changes:
            name = changes["name"].strip()
            if ch.kind == "channel" and len(name) < 2:
                raise AppError(422, "name_required", "Give the channel a name (at least 2 characters).")
            ch.name = name
        if "description" in changes:
            ch.description = changes["description"].strip()

    after = {"name": ch.name, "description": ch.description, "archived": ch.archived_at is not None}
    if after != before:
        action = ("chat.channel_archived" if after["archived"] and not before["archived"]
                  else "chat.channel_unarchived" if before["archived"] and not after["archived"]
                  else "chat.channel_updated")
        audit_service.record(db, actor=user, action=action, entity_type="chat_channel", entity_id=ch.id,
                             before=before, after=after)
    await db.commit()
    await _push(db, ch.id, {"type": "channel.changed"})
    return await get_channel(db, user, ch.id)


async def add_members(db: AsyncSession, user: User, channel_id: int, user_ids: list[int]) -> dict:
    """Channel: owner only. Group chat: any member. Already-members are skipped."""
    ch, me = await _membership(db, channel_id, user.id)
    _not_dm(ch)
    _not_archived(ch)
    if ch.kind == "channel":
        _must_own(me)
    new = await _active_users(db, user_ids, exclude=user.id)
    if new:
        await db.execute(
            pg_insert(ChatMember)
            .values([{"channel_id": ch.id, "user_id": uid, "role": "member"} for uid in new])
            .on_conflict_do_nothing(constraint="uq_chat_members_channel_user")
        )
    await db.commit()
    await _push(db, ch.id, {"type": "channel.changed"})
    return await get_channel(db, user, ch.id)


async def remove_member(db: AsyncSession, user: User, channel_id: int, user_id: int) -> None:
    """Remove someone (owner only), or leave (user_id = me). See rule 7 for the last owner / last person."""
    ch, me = await _membership(db, channel_id, user.id)
    _not_dm(ch)
    _not_archived(ch)
    leaving = user_id == user.id
    if not leaving:
        _must_own(me)
    target = me if leaving else await db.scalar(
        select(ChatMember).where(ChatMember.channel_id == ch.id, ChatMember.user_id == user_id))
    if target is None:
        raise AppError(404, "not_a_member", "That person isn't in this chat.")

    await db.delete(target)
    await db.flush()
    left = (await db.scalars(
        select(ChatMember).where(ChatMember.channel_id == ch.id).order_by(ChatMember.id))).all()
    if not left:
        ch.archived_at = datetime.now(timezone.utc)
    elif target.role == "owner" and not any(m.role == "owner" for m in left):
        left[0].role = "owner"  # the longest-standing member takes over

    audit_service.record(db, actor=user, action="chat.member_left" if leaving else "chat.member_removed",
                         entity_type="chat_channel", entity_id=ch.id,
                         before={"user_id": target.user_id, "role": target.role},
                         after={"members_left": len(left)})
    await db.commit()
    await _push(db, ch.id, {"type": "channel.changed"}, also=(target.user_id,))


# ---------- Messages (day 2) ----------

def _msg_out(m: ChatMessage, sender_name: str) -> dict:
    deleted = m.deleted_at is not None
    return {"id": m.id, "channel_id": m.channel_id, "sender_id": m.sender_id, "sender_name": sender_name,
            "body": "" if deleted else m.body, "mentions": [] if deleted else m.mentions,
            "deleted": deleted, "edited_at": m.edited_at, "created_at": m.created_at}


def _clean_body(body: str) -> str:
    body = body.strip()
    if not body:
        raise AppError(422, "empty", "Type a message first.")
    return body


async def _valid_mentions(db: AsyncSession, channel_id: int, ids: list[int], me: int) -> list[int]:
    """Keep only people in this chat (not me). Anyone else is silently dropped."""
    wanted = {i for i in ids if i != me}
    if not wanted:
        return []
    found = await db.scalars(select(ChatMember.user_id).where(
        ChatMember.channel_id == channel_id, ChatMember.user_id.in_(wanted)))
    return sorted(found.all())


def _where(ch: ChatChannel, members: list[dict], user_id: int) -> str:
    """'#sales', 'a direct message' or the group's title: for notification texts."""
    if ch.kind == "channel":
        return f"#{ch.name}"
    if ch.kind == "dm":
        return "a direct message"
    return _title(ch, members, user_id)


async def _notify_mentions(db: AsyncSession, user: User, ch: ChatChannel, ids: list[int], body: str) -> None:
    if not ids:
        return
    members = (await _members_of(db, [ch.id]))[ch.id]
    notification_service.notify(db, ids, "chat.mention", f"{user.name} mentioned you in {_where(ch, members, ids[0])}",
                                body=body[:200], link=f"/employee/chat?c={ch.id}")


async def list_messages(db: AsyncSession, user: User, channel_id: int, *, before: int | None = None,
                        after: int | None = None, limit: int = 50) -> dict:
    """Oldest first, `limit` at a time (cursor pagination: ids, not page numbers, so new messages
    arriving meanwhile never shift what you get).
    1. Neither: the newest messages (opening a chat).
    2. before=X: the ones just before X (scrolling up).
    3. after=X: the ones just after X (catching up after a dropped connection).
    has_more: there are more in that direction."""
    await _membership(db, channel_id, user.id)
    limit = max(1, min(limit, PAGE_MAX))
    q = (select(ChatMessage, User.name).join(User, User.id == ChatMessage.sender_id)
         .where(ChatMessage.channel_id == channel_id))
    if after is not None:
        q = q.where(ChatMessage.id > after).order_by(ChatMessage.id)
    else:
        if before is not None:
            q = q.where(ChatMessage.id < before)
        q = q.order_by(ChatMessage.id.desc())
    rows = (await db.execute(q.limit(limit + 1))).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    if after is None:
        rows.reverse()
    return {"messages": [_msg_out(m, name) for m, name in rows], "has_more": has_more}


async def send_message(db: AsyncSession, user: User, channel_id: int, body: str, mention_ids: list[int]) -> dict:
    ch, me = await _membership(db, channel_id, user.id)
    _not_archived(ch)
    body = _clean_body(body)
    key = f"user:{user.id}"
    if chat_send_limiter.blocked(key):
        raise AppError(429, "too_many", "You're sending messages too fast. Wait a moment and try again.")
    chat_send_limiter.hit(key)

    m = ChatMessage(channel_id=ch.id, sender_id=user.id, body=body, created_at=datetime.now(timezone.utc),
                    mentions=await _valid_mentions(db, ch.id, mention_ids, user.id))
    db.add(m)
    await db.flush()  # gives m.id
    me.last_read_message_id = m.id  # my own message is never unread for me
    await _notify_mentions(db, user, ch, m.mentions, body)
    await db.commit()
    out = _msg_out(m, user.name)
    await _push(db, ch.id, {"type": "message.new", "message": out})
    return out


async def _my_message(db: AsyncSession, user: User, message_id: int) -> tuple[ChatMessage, ChatChannel]:
    """My own message in a chat I'm still in, or 404 (someone else's looks the same as a missing one)."""
    row = (await db.execute(
        select(ChatMessage, ChatChannel)
        .join(ChatChannel, ChatChannel.id == ChatMessage.channel_id)
        .join(ChatMember, and_(ChatMember.channel_id == ChatChannel.id, ChatMember.user_id == user.id))
        .where(ChatMessage.id == message_id, ChatMessage.sender_id == user.id)
    )).first()
    if row is None:
        raise AppError(404, "not_found", "Message not found.")
    return row[0], row[1]


async def edit_message(db: AsyncSession, user: User, message_id: int, body: str, mention_ids: list[int]) -> dict:
    """Only people newly @mentioned by the edit get a notification."""
    m, ch = await _my_message(db, user, message_id)
    _not_archived(ch)
    if m.deleted_at is not None:
        raise AppError(409, "deleted", "This message was deleted.")
    old = set(m.mentions)
    m.body = _clean_body(body)
    m.mentions = await _valid_mentions(db, ch.id, mention_ids, user.id)
    m.edited_at = datetime.now(timezone.utc)
    await _notify_mentions(db, user, ch, [i for i in m.mentions if i not in old], m.body)
    await db.commit()
    out = _msg_out(m, user.name)
    await _push(db, ch.id, {"type": "message.edited", "message": out})
    return out


async def delete_message(db: AsyncSession, user: User, message_id: int) -> None:
    """Soft delete: the row stays (so replies and the order still make sense), the text is wiped."""
    m, ch = await _my_message(db, user, message_id)
    _not_archived(ch)
    if m.deleted_at is None:
        m.deleted_at, m.body, m.mentions = datetime.now(timezone.utc), "", []
        await db.commit()
        await _push(db, ch.id, {"type": "message.deleted", "message_id": m.id})


async def mark_read(db: AsyncSession, user: User, channel_id: int, message_id: int | None = None) -> None:
    """Read up to message_id (default: the newest). Never moves backwards, never past the newest."""
    ch, me = await _membership(db, channel_id, user.id)
    newest = await db.scalar(select(func.max(ChatMessage.id)).where(ChatMessage.channel_id == ch.id)) or 0
    target = min(message_id if message_id is not None else newest, newest)
    await db.execute(
        update(ChatMember)
        .where(ChatMember.id == me.id, ChatMember.last_read_message_id < target)
        .values(last_read_message_id=target)
    )
    await db.commit()
    await hub.push([user.id], {"type": "read", "channel_id": ch.id, "message_id": target})  # my other tabs
