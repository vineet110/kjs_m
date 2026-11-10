"""KJS Chat, phase 1 day 1: channels, group chats, DMs and their members.

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
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.chat import ChatChannel, ChatMember
from app.models.user import User
from app.services import audit_service


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

async def my_channels(db: AsyncSession, user: User) -> list[dict]:
    """My channels, then group chats and DMs. Unread counts come on day 2."""
    rows = (await db.execute(
        select(ChatChannel, ChatMember)
        .join(ChatMember, ChatMember.channel_id == ChatChannel.id)
        .where(ChatMember.user_id == user.id)
    )).all()
    members = await _members_of(db, [ch.id for ch, _ in rows])
    out = [_out(ch, me, members[ch.id], user.id) for ch, me in rows]
    out.sort(key=lambda c: (c["kind"] != "channel", c["archived"], c["title"].lower()))
    return out


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
