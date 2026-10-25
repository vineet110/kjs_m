"""Leads: capture from the website/Koko, SLA timers, notes, hand-over, escalation.

SLA (config/sla.ini): respond (first "contacted") within respond_minutes, close within
resolve_minutes. The clock only runs in working hours (shift_start–shift_end in
config/app.ini, Mon–Sat minus holidays), so a lead that arrives on Saturday night is
due on Monday morning, not "overdue" at midnight.
"""
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.ini import cfg
from app.core.errors import AppError
from app.core.permissions import effective_permissions
from app.core.rate_limit import lead_limiter
from app.jobs.runner import job
from app.models.catalog import Category, Product
from app.models.lead import Lead, LeadNote
from app.models.user import User
from app.schemas.lead import LeadIn, LeadOut
from app.services import audit_service, koko_service, notification_service
from app.services.attendance_service import local_day, to_utc
from app.services.calendar_service import CalendarService, holiday_set

log = logging.getLogger(__name__)
DUE_SOON_MINUTES = 5


# ---------- SLA maths (pure functions, unit tested) ----------
def _work_window(day: date) -> tuple[datetime, datetime]:
    c = cfg().app
    return to_utc(day, c.shift_start), to_utc(day, c.shift_end)


def add_work_minutes(start: datetime, minutes: int, holidays: set[date]) -> datetime:
    """`start` + `minutes` of working time (skips nights, Sundays and holidays)."""
    day, left, cursor = local_day(start), timedelta(minutes=minutes), start
    for _ in range(400):  # safety: never loop forever on a bad config
        if CalendarService.is_working_day(day, holidays):
            open_, close = _work_window(day)
            cursor = max(cursor, open_)
            if cursor < close:
                if cursor + left <= close:
                    return cursor + left
                left -= close - cursor
        day += timedelta(days=1)
        cursor = _work_window(day)[0]
    return cursor


def sla(lead: Lead, now: datetime, holidays: set[date]) -> dict:
    s = cfg().sla
    respond_due = add_work_minutes(lead.created_at, s.respond_minutes, holidays)
    resolve_due = add_work_minutes(lead.created_at, s.resolve_minutes, holidays)
    if lead.status == "closed":
        return {"sla_state": "done", "sla_label": "Closed", "respond_due_at": respond_due, "resolve_due_at": resolve_due}
    stage, due = ("Respond", respond_due) if lead.status == "new" else ("Resolve", resolve_due)
    mins = int((due - now).total_seconds() // 60)
    if mins < 0:
        state, label = "overdue", f"{stage} overdue by {_human(-mins)}"
    elif mins <= DUE_SOON_MINUTES:
        state, label = "due_soon", f"{stage} in {_human(mins)}"
    else:
        state, label = "ok", f"{stage} in {_human(mins)}"
    return {"sla_state": state, "sla_label": label, "respond_due_at": respond_due, "resolve_due_at": resolve_due}


def _human(mins: int) -> str:
    if mins < 60:
        return f"{mins} min"
    if mins < 60 * 24:
        return f"{mins // 60} h {mins % 60} min"
    return f"{mins // (60 * 24)} d"


# ---------- Capture ----------
async def create(db: AsyncSession, data: LeadIn, ip_hash: str | None) -> Lead | None:
    if data.website:  # honeypot filled = bot. Pretend success, save nothing.
        return None
    lead_limiter.check(ip_hash)

    product_id = category_id = None
    if data.product_slug:
        p = await db.scalar(select(Product).where(Product.slug == data.product_slug))
        if p:
            product_id, category_id = p.id, p.category_id
    if data.category_slug and category_id is None:
        category_id = await db.scalar(select(Category.id).where(Category.slug == data.category_slug))

    summary = await koko_service.summarise_chat(data.chat) if data.source == "koko" and data.chat else ""
    lead = Lead(
        source=data.source, name=data.name.strip(), company=data.company.strip(),
        email=data.email or "", phone=data.phone.strip(), country=data.country.strip(),
        buyer_type=data.buyer_type, product_id=product_id, category_id=category_id,
        quantity=data.quantity, message=data.message.strip(), chat_summary=summary,
        source_page=data.source_page, consent=True, consent_at=datetime.now(timezone.utc),
        ip_hash=ip_hash, status="new",
    )
    db.add(lead)
    await db.flush()
    audit_service.record(db, actor=None, action="lead.created", entity_type="lead",
                         entity_id=lead.id, after={"source": lead.source}, ip_hash=ip_hash)
    who = f"{lead.name}{f' ({lead.company})' if lead.company else ''}"
    notification_service.notify(db, await notification_service.users_with(db, "leads.view_all"),
                                "lead.new", f"New lead: {who}", lead.message[:300] or lead.chat_summary[:300],
                                "/admin/leads")
    await db.commit()
    log.info("lead.created", extra={"lead_id": lead.id, "source": lead.source})
    return lead


# ---------- Reading ----------
def _can_see_all(user: User) -> bool:
    return "leads.view_all" in effective_permissions(user.role, user.permissions)


async def list_for(db: AsyncSession, user: User, status: str | None = None, owner: int | None = None,
                   sla_state: str | None = None, all_leads: bool = False, limit: int = 200) -> list[LeadOut]:
    owner_user = User.__table__.alias("owner")
    notes = select(LeadNote.lead_id, func.count().label("n")).group_by(LeadNote.lead_id).subquery()
    q = (
        select(Lead, Product.name, Category.name, owner_user.c.name, notes.c.n)
        .outerjoin(Product, Product.id == Lead.product_id)
        .outerjoin(Category, Category.id == Lead.category_id)
        .outerjoin(owner_user, owner_user.c.id == Lead.assigned_to)
        .outerjoin(notes, notes.c.lead_id == Lead.id)
        .order_by(Lead.created_at.desc())
        .limit(limit)
    )
    if not (all_leads and _can_see_all(user)):
        # My leads + unassigned ones anyone may pick up.
        q = q.where((Lead.assigned_to == user.id) | (Lead.assigned_to.is_(None)))
    if status:
        q = q.where(Lead.status == status)
    if owner:
        q = q.where(Lead.assigned_to == owner)
    now = datetime.now(timezone.utc)
    holidays = await holiday_set(db, now.year - 1, now.year + 1)
    out = []
    for lead, product_name, category_name, owner_name, note_count in (await db.execute(q)).all():
        timers = sla(lead, now, holidays)
        if sla_state and timers["sla_state"] != sla_state:
            continue
        out.append(LeadOut(
            id=lead.id, source=lead.source, name=lead.name, company=lead.company, email=lead.email,
            phone=lead.phone, country=lead.country, buyer_type=lead.buyer_type, quantity=lead.quantity,
            message=lead.message, chat_summary=lead.chat_summary, source_page=lead.source_page,
            status=lead.status, product_name=product_name, category_name=category_name,
            created_at=lead.created_at, assigned_to=lead.assigned_to, owner_name=owner_name,
            responded_at=lead.responded_at, resolved_at=lead.resolved_at, outcome=lead.outcome,
            note_count=note_count or 0, **timers,
        ))
    return out


async def _lead_for(db: AsyncSession, user: User, lead_id: int) -> Lead:
    lead = await db.get(Lead, lead_id)
    if lead is None or not (_can_see_all(user) or lead.assigned_to in (None, user.id)):
        raise AppError(404, "not_found", "Lead not found.")
    return lead


# ---------- Working a lead ----------
async def set_status(db: AsyncSession, user: User, lead_id: int, status: str, outcome: str = "") -> None:
    lead = await _lead_for(db, user, lead_id)
    before = {"status": lead.status, "assigned_to": lead.assigned_to}
    now = datetime.now(timezone.utc)
    lead.status = status
    if status in ("contacted", "closed") and lead.responded_at is None:
        lead.responded_at = now  # stops the "respond" timer
    if status == "closed":
        lead.resolved_at = now  # stops the "resolve" timer
        lead.outcome = outcome or lead.outcome
    if status == "new":
        lead.resolved_at = None
    if lead.assigned_to is None:
        lead.assigned_to = user.id  # whoever acts on an unassigned lead takes it
    audit_service.record(db, actor=user, action="lead.status_changed", entity_type="lead",
                         entity_id=lead.id, before=before,
                         after={"status": status, "assigned_to": lead.assigned_to, "outcome": lead.outcome})
    if outcome:
        db.add(LeadNote(lead_id=lead.id, user_id=user.id, kind="outcome", text=outcome))
    await db.commit()


async def add_note(db: AsyncSession, user: User, lead_id: int, kind: str, text: str) -> None:
    lead = await _lead_for(db, user, lead_id)
    db.add(LeadNote(lead_id=lead.id, user_id=user.id, kind=kind, text=text.strip()))
    if kind in ("call", "email") and lead.status == "new":
        await set_status(db, user, lead_id, "contacted")  # logging a call/email = responded
        return
    await db.commit()


async def list_notes(db: AsyncSession, user: User, lead_id: int) -> list[dict]:
    await _lead_for(db, user, lead_id)
    rows = await db.execute(select(LeadNote, User.name).join(User, User.id == LeadNote.user_id)
                            .where(LeadNote.lead_id == lead_id).order_by(LeadNote.id))
    return [{"id": n.id, "kind": n.kind, "text": n.text, "user_name": name, "created_at": n.created_at}
            for n, name in rows.all()]


async def assign(db: AsyncSession, user: User, lead_id: int, to_user_id: int) -> None:
    """Hand over (owner) or reassign (leads.view_all) a lead to a colleague."""
    lead = await _lead_for(db, user, lead_id)
    target = await db.get(User, to_user_id)
    if target is None or target.status != "active":
        raise AppError(422, "bad_user", "Pick an active colleague.")
    if "leads.view" not in effective_permissions(target.role, target.permissions):
        raise AppError(422, "bad_user", f"{target.name} can't work on leads.")
    before = lead.assigned_to
    lead.assigned_to = target.id
    db.add(LeadNote(lead_id=lead.id, user_id=user.id, kind="handover", text=f"Assigned to {target.name}"))
    audit_service.record(db, actor=user, action="lead.assigned", entity_type="lead", entity_id=lead.id,
                         before={"assigned_to": before}, after={"assigned_to": target.id})
    if target.id != user.id:
        notification_service.notify(db, [target.id], "lead.assigned", f"Lead assigned to you: {lead.name}",
                                    f"From {user.name}.", "/employee/dashboard")
    await db.commit()


async def counts(db: AsyncSession) -> dict[str, int]:
    rows = await db.execute(select(Lead.status, func.count()).group_by(Lead.status))
    return {s: n for s, n in rows.all()}


# ---------- Escalation job ----------
@job("sla_check")
async def sla_check(db: AsyncSession, now: datetime | None = None) -> dict:
    """Tell the owner and admins once per breach (respond late, then resolve late). Safe to re-run:
    escalation_level remembers what was already reported."""
    now = now or datetime.now(timezone.utc)
    grace = timedelta(minutes=cfg().sla.escalate_after_minutes)
    holidays = await holiday_set(db, now.year - 1, now.year + 1)
    leads = (await db.scalars(select(Lead).where(Lead.status != "closed", Lead.escalation_level < 2))).all()
    managers = await notification_service.users_with(db, "leads.view_all")
    reported = 0
    for lead in leads:
        t = sla(lead, now, holidays)
        level, what = 0, ""
        if lead.status == "new" and lead.escalation_level < 1 and now > t["respond_due_at"] + grace:
            level, what = 1, "not answered"
        elif now > t["resolve_due_at"] + grace:
            level, what = 2, "not closed"
        if not level:
            continue
        lead.escalation_level = level
        owner = await db.get(User, lead.assigned_to) if lead.assigned_to else None
        who = owner.name if owner else "nobody yet"
        notification_service.notify(
            db, set(managers) | ({owner.id} if owner else set()), "lead.sla_breach",
            f"Lead {what} in time: {lead.name}", f"{t['sla_label']}. Owner: {who}.", "/admin/leads")
        log.warning("lead.sla_breach", extra={"lead_id": lead.id, "level": level})
        reported += 1
    return {"open_leads": len(leads), "escalated": reported}
