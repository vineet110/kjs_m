"""GET /employee/updates: the portal's one cheap "anything new?" check (every 30 s while a tab is open).

Counters only, from a few COUNT queries. The page reloads a part (bell, approvals, chat, lead lists) only
when its number changed. A section is null when it is not this person's (no permission, or its portal
area is switched off), so the page shows no badge for it.
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.modules import visible
from app.core.permissions import effective_permissions
from app.models.attendance import Regularization
from app.models.chat import ChatMember, ChatMessage
from app.models.lead import Lead, LeadNote
from app.models.notification import Notification
from app.models.user import User
from app.services import chat_service, file_service

LEAD_SOURCES = {"koko": "koko", "internal": "internal"}  # badge -> lead source


async def counters(db: AsyncSession, user: User) -> dict:
    perms = effective_permissions(user.role, user.permissions)
    count = lambda q: db.scalar(select(func.count()).select_from(q.subquery()))  # noqa: E731

    out: dict = {"notifications": await db.scalar(
        select(func.count()).select_from(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None)))}

    # Approvals: the same three sections as the All approvals page (and the sidebar badge)
    approvals = 0
    if "staff.approve" in perms:
        approvals += await count(select(User.id).where(User.status == "pending"))
    if "attendance.manage" in perms and visible(user, "attendance"):
        approvals += await count(select(Regularization.id).where(Regularization.status == "pending"))
    if "files.approve" in perms:
        approvals += len(await file_service.delete_requests(db, user))  # keeps its own hidden-area rule
    out["approvals"] = approvals if perms & {"staff.approve", "attendance.manage", "files.approve"} else None

    out["chat"] = await chat_service.unread_total(db, user) if visible(user, "chat") else None
    # The newest message in any of my chats (muted ones too). The chat page catches up when it changes: the
    # unread number alone misses muted chats and also moves when I read (CodeRabbit / review on #76).
    out["chat_last"] = await db.scalar(
        select(func.max(ChatMessage.id)).join(ChatMember, ChatMember.channel_id == ChatMessage.channel_id)
        .where(ChatMember.user_id == user.id)) if visible(user, "chat") else None

    # New (not yet contacted) leads this person can see: everyone's with leads.view_all, else their own
    # plus unassigned ones (the same rule as the lead lists)
    if "leads.view" in perms:
        new = select(Lead.source, func.count()).where(Lead.status == "new").group_by(Lead.source)
        if "leads.view_all" not in perms:
            new = new.where((Lead.assigned_to == user.id) | (Lead.assigned_to.is_(None)))
        by_source = dict((await db.execute(new)).all())
        out["leads"] = {"all": sum(by_source.values())} | {k: by_source.get(s, 0) for k, s in LEAD_SOURCES.items()}
        # `changed` = when any lead last changed (status, owner, SLA) or got a note. The lists reload on it,
        # the badges use the counts: one lead leaving "new" while another arrives keeps every count equal
        # (CodeRabbit on #76). Over ALL leads, so a lead handed away from you still refreshes your list; it
        # is only a time, nothing about the lead.
        # Both are index lookups: ix_leads_updated_at (migration 0023) and the notes' primary key
        last_lead = await db.scalar(select(func.max(Lead.updated_at)))
        last_note = await db.scalar(select(func.max(LeadNote.id)))
        out["leads"]["changed"] = f"{last_lead.isoformat() if last_lead else ''}|{last_note or 0}"
    else:
        out["leads"] = None
    return out
