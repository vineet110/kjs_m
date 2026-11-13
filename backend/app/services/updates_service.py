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
from app.models.lead import Lead
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

    # New (not yet contacted) leads this person can see: everyone's with leads.view_all, else their own
    # plus unassigned ones (the same rule as the lead lists)
    if "leads.view" in perms:
        new = select(Lead.source, func.count()).where(Lead.status == "new").group_by(Lead.source)
        if "leads.view_all" not in perms:
            new = new.where((Lead.assigned_to == user.id) | (Lead.assigned_to.is_(None)))
        by_source = dict((await db.execute(new)).all())
        out["leads"] = {"all": sum(by_source.values())} | {k: by_source.get(s, 0) for k, s in LEAD_SOURCES.items()}
    else:
        out["leads"] = None
    return out
