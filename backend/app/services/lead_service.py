"""Leads: capture from the website/Koko, SLA timers, notes, hand-over, escalation.

SLA (config/sla.ini): respond (first "contacted") within respond_minutes, close within
resolve_minutes. The clock only runs in working hours (shift_start–shift_end in
config/app.ini, Mon–Sat minus holidays), so a lead that arrives on Saturday night is
due on Monday morning, not "overdue" at midnight.
"""
import asyncio
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
from app.models.task import Task
from app.models.user import User
from app.schemas.lead import InternalLeadIn, LeadIn, LeadOut
from app.services import (audit_service, file_service, koko_service, lead_reader, notification_service,
                          task_service)
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
FEATURE_OF_SOURCE = {"koko": "koko", "configurator": "configurator"}  # lead source -> features.ini switch
async def create(db: AsyncSession, data: LeadIn, ip_hash: str | None, rate_key: str | None = None) -> Lead | None:
    if data.website:  # honeypot filled = bot. Pretend success, save nothing.
        return None
    # A source whose feature is switched off (config/features.ini) is refused, not only hidden (CR8)
    flag = FEATURE_OF_SOURCE.get(data.source)
    if flag and not getattr(cfg().features, flag):
        raise AppError(404, "feature_off", "This form is not available right now.")
    lead_limiter.check(rate_key or ip_hash)
    # The AI summary first, before any database query: an LLM call takes seconds, and holding a
    # database connection that long would starve other requests when several visitors chat.
    summary = await koko_service.summarise_chat(data.chat) if data.source == "koko" and data.chat else ""

    product_id = category_id = None
    if data.product_slug:
        p = await db.scalar(select(Product).where(Product.slug == data.product_slug))
        if p:
            product_id, category_id = p.id, p.category_id
    if data.category_slug and category_id is None:
        category_id = await db.scalar(select(Category.id).where(Category.slug == data.category_slug))

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
                   sla_state: str | None = None, all_leads: bool = False, limit: int = 200,
                   offset: int = 0, source: str | None = None, lead_ids: list[int] | None = None) -> list[LeadOut]:
    owner_user = User.__table__.alias("owner")
    creator = User.__table__.alias("creator")
    notes = select(LeadNote.lead_id, func.count().label("n")).group_by(LeadNote.lead_id).subquery()
    q = (
        select(Lead, Product.name, Category.name, owner_user.c.name, notes.c.n, creator.c.name)
        .outerjoin(Product, Product.id == Lead.product_id)
        .outerjoin(Category, Category.id == Lead.category_id)
        .outerjoin(owner_user, owner_user.c.id == Lead.assigned_to)
        .outerjoin(creator, creator.c.id == Lead.created_by)
        .outerjoin(notes, notes.c.lead_id == Lead.id)
        .order_by(Lead.created_at.desc())
        .limit(limit)
        .offset(offset)  # older pages: ?offset=500
    )
    if not (all_leads and _can_see_all(user)):
        # My leads + unassigned ones anyone may pick up.
        q = q.where((Lead.assigned_to == user.id) | (Lead.assigned_to.is_(None)))
    if status:
        q = q.where(Lead.status == status)
    if sla_state and sla_state != "done":
        # Only open leads can be overdue / due soon. Filter them in SQL and look past the newest
        # `limit` rows, otherwise an old overdue lead would vanish from the "overdue" list.
        q = q.where(Lead.status != "closed").limit(2000)
    if owner:
        q = q.where(Lead.assigned_to == owner)
    if source:
        q = q.where(Lead.source == source)
    if lead_ids is not None:
        q = q.where(Lead.id.in_(lead_ids))
    now = datetime.now(timezone.utc)
    holidays = await holiday_set(db, now.year - 1, now.year + 1)
    out = []
    for lead, product_name, category_name, owner_name, note_count, creator_name in (await db.execute(q)).all():
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
            note_count=note_count or 0, updated_at=lead.updated_at, created_by_name=creator_name, **timers,
        ))
    return out


# ---------- Lead management: contacts, one lead, internal leads, tasks on a lead ----------
def _match_keys(lead: Lead) -> list[str]:
    """What ties a lead to a person: its full phone number (every digit, country code included, so
    "+91 98765 43210" and "+1 98765 43210" stay two people) and its email."""
    keys = []
    digits = "".join(ch for ch in lead.phone if ch in "0123456789")
    if len(digits) >= 6:
        keys.append(f"p:{digits}")
    if lead.email:
        keys.append(f"e:{lead.email.lower()}")
    return keys


def group_contacts(leads: list[Lead]) -> list[list[Lead]]:
    """Leads of the same person, grouped. Two leads are one person when they share the phone OR the email,
    also through a third lead (A and B share a phone, B and C an email: all three are one person).
    Keeps the order given (newest first), inside each group and between groups."""
    parent = list(range(len(leads)))  # "union-find": each lead points towards its group's first lead

    def top(i: int) -> int:
        while parent[i] != i:
            i = parent[i]
        return i

    first_with: dict[str, int] = {}
    for i, lead in enumerate(leads):
        for k in _match_keys(lead):
            a, b = top(i), top(first_with.setdefault(k, i))
            parent[max(a, b)] = min(a, b)  # the newer lead stays the group's head
    groups: dict[int, list[Lead]] = {}
    for i, lead in enumerate(leads):
        groups.setdefault(top(i), []).append(lead)
    return list(groups.values())


def _visible(q, user: User):
    """Leads this person may see: all (leads.view_all), else their own + unassigned ones."""
    if _can_see_all(user):
        return q
    return q.where((Lead.assigned_to == user.id) | (Lead.assigned_to.is_(None)))


async def contacts(db: AsyncSession, user: User) -> list[dict]:
    """One row per person, newest first. Grouped in Python (group_contacts): a few thousand leads is
    nothing, and "same phone or same email" is easier to read here than in SQL."""
    q = _visible(select(Lead).order_by(Lead.created_at.desc(), Lead.id.desc()), user).limit(5000)
    out = []
    for g in group_contacts(list((await db.scalars(q)).all())):
        newest = g[0]  # its name / phone are the ones shown
        inactive = sum(x.status == "closed" for x in g)
        out.append({"lead_id": newest.id, "name": newest.name, "phone": newest.phone,
                    # an older enquiry may carry the email the newest one left out
                    "email": next((x.email for x in g if x.email), newest.email),
                    "active": len(g) - inactive, "inactive": inactive, "total": len(g), "last_at": newest.created_at})
    return out


async def contact_detail(db: AsyncSession, user: User, lead_id: int) -> dict:
    """One lead, with every other enquiry of the same person (for the contact page)."""
    lead = await _lead_for(db, user, lead_id)
    # Same grouping as the contacts list, so both always agree on who belongs to whom
    q = _visible(select(Lead).order_by(Lead.created_at.desc(), Lead.id.desc()), user).limit(5000)
    groups = group_contacts(list((await db.scalars(q)).all()))
    same = next(([x.id for x in g] for g in groups if any(x.id == lead.id for x in g)), [])
    rows = await list_for(db, user, all_leads=True, limit=200, lead_ids=same or [lead.id])
    this = next((r for r in rows if r.id == lead.id), None)
    if this is None:  # can see it (checked above) but the list didn't bring it: never expected
        raise AppError(404, "not_found", "Lead not found.")
    return {"lead": this, "enquiries": rows}


async def create_internal(db: AsyncSession, user: User, data: InternalLeadIn) -> LeadOut:
    """A lead a staff member types in. Source "internal", theirs from the start (assigned + created by them).
    No visitor ticked a consent box: the staff member spoke to the buyer, and that conversation is the consent
    (an assumption, noted for KJS to confirm)."""
    category_id = None
    if data.category_slug:
        category_id = await db.scalar(select(Category.id).where(Category.slug == data.category_slug))
    lead = Lead(
        source="internal", name=data.name.strip(), company=data.company.strip(), email=data.email or "",
        phone=data.phone.strip(), country=data.country.strip(), buyer_type=data.buyer_type,
        category_id=category_id, quantity=data.quantity, message=data.message.strip(),
        source_page="", consent=True, consent_at=datetime.now(timezone.utc), ip_hash=None, status="new",
        assigned_to=user.id, created_by=user.id,
    )
    db.add(lead)
    await db.flush()
    audit_service.record(db, actor=user, action="lead.created", entity_type="lead", entity_id=lead.id,
                         after={"source": "internal", "assigned_to": user.id})
    await db.commit()
    log.info("lead.created", extra={"lead_id": lead.id, "source": "internal"})
    return (await list_for(db, user, all_leads=True, limit=1, lead_ids=[lead.id]))[0]


async def read_lead_file(db: AsyncSession, filename: str, data: bytes) -> dict:
    """An Excel / CSV file read for the New internal lead form (see lead_reader). Nothing is saved."""
    cats = (await db.scalars(select(Category))).all()
    names = {c.slug.lower(): c.slug for c in cats} | {c.name.lower(): c.slug for c in cats}
    out = await asyncio.to_thread(lead_reader.read, filename, data, names)  # openpyxl is slow and blocking
    # Counts only: the values are customers' personal data, which never go in the logs
    log.info("lead.file_read", extra={"leads": len(out["leads"]), "more_rows": out["more_rows"]})
    return out


async def same_person(db: AsyncSession, user: User, phone: str, email: str) -> dict:
    """Before saving a lead: does this person already have leads (same phone or email, the Contacts rule)?
    Only leads this user may see are counted, so it never tells anyone about someone else's buyers."""
    probe = Lead(phone=phone.strip()[:40], email=email.strip()[:255])  # never added to the database
    if not _match_keys(probe):
        return {"count": 0, "lead_id": None}
    q = _visible(select(Lead).order_by(Lead.created_at.desc(), Lead.id.desc()), user).limit(5000)
    for group in group_contacts([probe, *(await db.scalars(q)).all()]):
        if group[0] is probe:
            rest = group[1:]
            return {"count": len(rest), "lead_id": rest[0].id if rest else None}
    return {"count": 0, "lead_id": None}


async def lead_tasks(db: AsyncSession, user: User, lead_id: int) -> list[dict]:
    """Tasks made from this lead (anyone's: whoever may see the lead sees what is planned on it)."""
    await _lead_for(db, user, lead_id)
    rows = (await db.scalars(select(Task).where(Task.source == "lead", Task.source_ref == f"lead:{lead_id}")
                             .order_by(Task.status == "done", Task.due_at.is_(None), Task.due_at, Task.id.desc()))).all()
    names = dict((await db.execute(select(User.id, User.name))).all())
    now = datetime.now(timezone.utc)
    return [task_service.task_out(t, names, now) for t in rows]


async def add_lead_task(db: AsyncSession, user: User, lead_id: int, title: str, notes: str,
                        due_at: datetime | None) -> dict:
    """A to-do on this lead, for me. It also shows in my Tasks page (source "lead")."""
    lead = await _lead_for(db, user, lead_id, lock=True)
    t = task_service.add(db, assignee_id=user.id, title=title.strip(), notes=notes.strip(), due_at=due_at,
                         source="lead", source_ref=f"lead:{lead.id}", created_by=user.id)
    await db.flush()
    audit_service.record(db, actor=user, action="task.created", entity_type="task", entity_id=t.id,
                         after={"title": t.title, "lead_id": lead.id})
    await db.commit()
    return task_service.task_out(t, {user.id: user.name}, datetime.now(timezone.utc))


async def _lead_for(db: AsyncSession, user: User, lead_id: int, lock: bool = False) -> Lead:
    # lock=True for changes: if two people take the same unassigned lead at once, the second waits,
    # then sees it is no longer unassigned and gets "not found" instead of silently overwriting.
    lead = await db.get(Lead, lead_id, with_for_update=lock, populate_existing=lock)
    if lead is None or not (_can_see_all(user) or lead.assigned_to in (None, user.id)):
        raise AppError(404, "not_found", "Lead not found.")
    return lead


def _lead_id(owner_id: str) -> int | None:
    """'7' and '007' -> 7. Anything else ('abc', '²', a number too big for the database) -> None."""
    if not (owner_id.isascii() and owner_id.isdigit()) or len(owner_id) > 10:
        return None
    n = int(owner_id)
    return n if 0 < n <= 2**31 - 1 else None  # leads.id is a database "integer"


def _clean_lead_id(owner_id: str) -> str:
    n = _lead_id(owner_id)
    return str(n) if n else owner_id  # a bad id stays as it is, and the access check then refuses it


async def _files_access(db: AsyncSession, user: User, owner_id: str, action: str) -> bool:
    """Files on a lead (a visiting card, a price list): whoever can see the lead can see its files.
    Adding or asking to delete needs the lead to be yours (or leads.view_all), not just unassigned."""
    lead_id = _lead_id(owner_id)
    if "leads.view" not in effective_permissions(user.role, user.permissions) or lead_id is None:
        return False
    try:
        lead = await _lead_for(db, user, lead_id)
    except AppError:
        return False
    return action == "read" or lead.assigned_to == user.id or _can_see_all(user)


file_service.register_owner("lead", _files_access, clean=_clean_lead_id)


# ---------- Working a lead ----------
async def set_status(db: AsyncSession, user: User, lead_id: int, status: str, outcome: str = "") -> None:
    lead = await _lead_for(db, user, lead_id, lock=True)
    # Status rules: the timers (responded_at, resolved_at) must always match the status.
    if status == lead.status:
        raise AppError(409, "unchanged", f"This lead is already '{status}'.")
    if status == "new" and lead.responded_at is not None:
        raise AppError(409, "already_answered", "This lead was already answered; set it to 'contacted' instead.")
    before = {"status": lead.status, "assigned_to": lead.assigned_to}
    now = datetime.now(timezone.utc)
    lead.status = status
    if status in ("contacted", "closed") and lead.responded_at is None:
        lead.responded_at = now  # stops the "respond" timer
    if status == "closed":
        lead.resolved_at = now  # stops the "resolve" timer
        lead.outcome = outcome or lead.outcome
    else:
        lead.resolved_at = None  # re-opened: the "resolve" timer runs again
    if lead.assigned_to is None:
        lead.assigned_to = user.id  # whoever acts on an unassigned lead takes it
    audit_service.record(db, actor=user, action="lead.status_changed", entity_type="lead",
                         entity_id=lead.id, before=before,
                         after={"status": status, "assigned_to": lead.assigned_to, "outcome": lead.outcome})
    if outcome:
        db.add(LeadNote(lead_id=lead.id, user_id=user.id, kind="outcome", text=outcome))
    await db.commit()


async def add_note(db: AsyncSession, user: User, lead_id: int, kind: str, text: str) -> None:
    lead = await _lead_for(db, user, lead_id, lock=True)
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
    lead = await _lead_for(db, user, lead_id, lock=True)
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


async def weekly_counts(db: AsyncSession, now: datetime | None = None) -> tuple[int, int]:
    """Leads received in the last 7 days, and in the 7 days before that (rolling windows, so no
    week-start or time zone question). Feeds the trend arrow on the admin overview."""
    now = now or datetime.now(timezone.utc)
    week_ago, two_weeks_ago = now - timedelta(days=7), now - timedelta(days=14)

    async def between(start: datetime, end: datetime) -> int:
        q = select(func.count()).select_from(Lead).where(Lead.created_at >= start, Lead.created_at < end)
        return await db.scalar(q) or 0

    return await between(week_ago, now), await between(two_weeks_ago, week_ago)


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
