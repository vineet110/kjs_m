"""Work pages (Team work for admins, My work for employees): what one person did, read-only.

Everything here only READS existing tables. The sources of the timeline:
- lead_notes: calls, emails, notes, hand-overs and lead outcomes (one table, `kind` tells them apart)
- tasks: tasks finished (completed_at), with their outcome
- chat_messages: messages sent (not deleted ones)
- attendance_punches: check-in and check-out
Migration 0027 indexes each of them by (person, time), so one person's range is a short lookup.

Days are IST days (config app.timezone): a call at 00:30 IST belongs to that day, not the day before.
"""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.ini import cfg
from app.core.errors import AppError
from app.models.attendance import Attendance, AttendancePunch
from app.models.audit import AuditLog
from app.models.chat import ChatChannel, ChatMessage
from app.models.lead import Lead, LeadNote
from app.models.monitor import Break, IdlePeriod, Screenshot, ShareEvent
from app.models.task import Task
from app.models.user import User
from app.services import attendance_service as att
from app.services import audit_service
from app.services.task_service import task_out

# Range limit, page size and refresh time: config/monitoring.ini (read with cfg() each time, so edits apply live)
KINDS = ("call", "email", "note", "outcome", "task", "chat", "attendance", "break", "idle", "screen")
IDLE_REASON = {"call": "On a call", "meeting": "In a meeting", "other": "Other"}
NOTE_KIND = {"call": "call", "email": "email", "note": "note", "handover": "note", "outcome": "outcome"}


# ---------- Dates ----------
def check_range(start: date, end: date) -> None:
    if end < start:
        raise AppError(400, "bad_range", "The end date is before the start date.")
    max_days = cfg().monitoring.max_range_days
    if (end - start).days + 1 > max_days:
        raise AppError(400, "bad_range", f"Pick at most {max_days} days.", {"max_days": max_days})


def utc_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    """[start 00:00 IST, the day after end 00:00 IST) in UTC."""
    return att.to_utc(start, "00:00"), att.to_utc(end + timedelta(days=1), "00:00")


# ---------- Counts (Team work table, Overview) ----------
async def _counts(db: AsyncSession, t0: datetime, t1: datetime, user_id: int | None = None) -> dict[int, dict]:
    """{user_id: {calls, emails, notes, outcomes, tasks_done, chat}} for everything done in [t0, t1)."""
    out: dict[int, dict] = {}

    def row(uid: int) -> dict:
        return out.setdefault(uid, {"calls": 0, "emails": 0, "notes": 0, "outcomes": 0, "tasks_done": 0, "chat": 0})

    q = (select(LeadNote.user_id, LeadNote.kind, func.count())
         .where(LeadNote.created_at >= t0, LeadNote.created_at < t1)
         .group_by(LeadNote.user_id, LeadNote.kind))
    if user_id is not None:
        q = q.where(LeadNote.user_id == user_id)
    for uid, kind, n in (await db.execute(q)).all():
        key = {"call": "calls", "email": "emails", "outcome": "outcomes"}.get(kind, "notes")
        row(uid)[key] += n

    q = (select(Task.assignee_id, func.count())
         .where(Task.status == "done", Task.completed_at >= t0, Task.completed_at < t1)
         .group_by(Task.assignee_id))
    if user_id is not None:
        q = q.where(Task.assignee_id == user_id)
    for uid, n in (await db.execute(q)).all():
        row(uid)["tasks_done"] = n

    q = (select(ChatMessage.sender_id, func.count())
         .where(ChatMessage.created_at >= t0, ChatMessage.created_at < t1, ChatMessage.deleted_at.is_(None))
         .group_by(ChatMessage.sender_id))
    if user_id is not None:
        q = q.where(ChatMessage.sender_id == user_id)
    for uid, n in (await db.execute(q)).all():
        row(uid)["chat"] = n
    return out


EMPTY = {"calls": 0, "emails": 0, "notes": 0, "outcomes": 0, "tasks_done": 0, "chat": 0}


async def team_day(db: AsyncSession, day: date) -> dict:
    """One row per active person: attendance (same numbers as Team attendance) plus what they did."""
    people = await att.team_day(db, day)
    counts = await _counts(db, *utc_bounds(day, day))
    live = await _live(db, day)
    rows = [{**p, **counts.get(p["user_id"], EMPTY), **live.get(p["user_id"], LIVE_EMPTY)} for p in people]
    in_now = sum(1 for p in rows if p["check_in"] and not p["check_out"])
    return {"day": day, "rows": rows, "refresh_seconds": cfg().monitoring.team_refresh_seconds,
            "summary": {"people": len(rows), "checked_in_now": in_now,
                        "checked_out": sum(1 for p in rows if p["check_out"]),
                        "not_in": sum(1 for p in rows if not p["check_in"]),
                        "on_break": sum(1 for p in rows if p["on_break"]),
                        "idle_now": sum(1 for p in rows if p["idle_minutes"])}}


LIVE_EMPTY = {"on_break": False, "break_minutes": 0, "idle_minutes": 0, "sharing": None, "device": None,
              "extension": "not_connected"}


async def _live(db: AsyncSession, day: date) -> dict[int, dict]:
    """Breaks, idle now, screen sharing and device per person for one day (Phase B)."""
    now = datetime.now(timezone.utc)
    t0, t1 = utc_bounds(day, day)
    warn = cfg().monitoring.idle_warn_minutes
    out: dict[int, dict] = {}

    def row(uid: int) -> dict:
        return out.setdefault(uid, dict(LIVE_EMPTY))

    for b in (await db.scalars(select(Break).where(Break.day == day))).all():
        r = row(b.user_id)
        r["break_minutes"] += _mins(b.started_at, b.ended_at or now)
        r["on_break"] = r["on_break"] or b.ended_at is None
    if day == att.local_day(now):  # "idle now" only means something for today
        for i in (await db.scalars(select(IdlePeriod).where(IdlePeriod.ended_at.is_(None)))).all():
            if _mins(i.started_at, now) >= warn:
                row(i.user_id)["idle_minutes"] = _mins(i.started_at, now)
    last = (select(ShareEvent.user_id, ShareEvent.state,
                   func.row_number().over(partition_by=ShareEvent.user_id,
                                          order_by=(ShareEvent.at.desc(), ShareEvent.id.desc())).label("n"))
            .where(ShareEvent.at >= t0, ShareEvent.at < t1).subquery())
    for uid, state in (await db.execute(select(last.c.user_id, last.c.state).where(last.c.n == 1))).all():
        row(uid)["sharing"] = state
    for uid, device in (await db.execute(select(Attendance.user_id, Attendance.device)
                                         .where(Attendance.day == day, Attendance.device.is_not(None)))).all():
        row(uid)["device"] = device
    return out


def _mins(a: datetime, b: datetime) -> int:
    return max(0, int((b - a).total_seconds() // 60))


async def person(db: AsyncSession, user_id: int) -> User:
    u = await db.get(User, user_id)
    if not u:
        raise AppError(404, "not_found", "No such staff member.")
    return u


async def overview(db: AsyncSession, u: User, start: date, end: date) -> dict:
    check_range(start, end)
    counts = (await _counts(db, *utc_bounds(start, end), user_id=u.id)).get(u.id, EMPTY)
    days = (await db.scalars(select(Attendance).where(
        Attendance.user_id == u.id, Attendance.day >= start, Attendance.day <= end))).all()
    t0, t1 = utc_bounds(start, end)
    now = datetime.now(timezone.utc)
    warn = cfg().monitoring.idle_warn_minutes
    breaks = (await db.scalars(select(Break).where(Break.user_id == u.id, Break.day >= start, Break.day <= end))).all()
    idles = (await db.scalars(select(IdlePeriod).where(IdlePeriod.user_id == u.id, IdlePeriod.started_at >= t0,
                                                       IdlePeriod.started_at < t1))).all()
    idle_mins = [_mins(i.started_at, i.ended_at or now) for i in idles]
    shots = await db.scalar(select(func.count()).select_from(Screenshot).where(
        Screenshot.user_id == u.id, Screenshot.taken_at >= t0, Screenshot.taken_at < t1))
    return {"user": {"id": u.id, "name": u.name, "email": u.email, "role": u.role},
            "from": start, "to": end, "today": await att.today(db, u),
            "extension": "not_connected",  # Phase C: the browser extension
            "totals": {**counts, "days_present": sum(1 for a in days if a.check_in_at),
                       "hours": round(sum(att.hours(a) for a in days), 2),
                       "break_minutes": sum(_mins(b.started_at, b.ended_at or now) for b in breaks),
                       "idle_minutes": sum(m for m in idle_mins if m >= warn), "screenshots": shots or 0}}


# ---------- Timeline ----------
async def timeline(db: AsyncSession, user_id: int, start: date, end: date,
                   kinds: set[str] | None = None, before: datetime | None = None) -> dict:
    """Newest first, full text. `before` (exclusive) asks for the next page."""
    check_range(start, end)
    kinds = kinds or set(KINDS)
    t0, t1 = utc_bounds(start, end)
    size = cfg().monitoring.timeline_page_size
    if before is not None:
        t1 = min(t1, before)
    items: list[dict] = []

    note_kinds = [k for k, v in NOTE_KIND.items() if v in kinds]
    if note_kinds:
        q = (select(LeadNote, Lead.name, Lead.company).join(Lead, Lead.id == LeadNote.lead_id)
             .where(LeadNote.user_id == user_id, LeadNote.kind.in_(note_kinds),
                    LeadNote.created_at >= t0, LeadNote.created_at < t1)
             .order_by(LeadNote.created_at.desc()).limit(size))
        for n, name, company in (await db.execute(q)).all():
            who = f"{name} · {company}" if company else name
            title = {"handover": "Hand-over", "outcome": "Lead outcome"}.get(n.kind, n.kind.capitalize())
            items.append({"kind": NOTE_KIND[n.kind], "at": n.created_at, "title": f"{title} · {who} (lead #{n.lead_id})",
                          "text": n.text, "lead_id": n.lead_id})

    if "task" in kinds:
        q = (select(Task).where(Task.assignee_id == user_id, Task.status == "done",
                                Task.completed_at >= t0, Task.completed_at < t1)
             .order_by(Task.completed_at.desc()).limit(size))
        for t in (await db.scalars(q)).all():
            text = "\n".join(x for x in (f"Outcome: {t.outcome}" if t.outcome else "", t.notes) if x)
            items.append({"kind": "task", "at": t.completed_at, "title": f"Task done · {t.title}", "text": text,
                          "task_id": t.id})

    if "chat" in kinds:
        q = (select(ChatMessage, ChatChannel).join(ChatChannel, ChatChannel.id == ChatMessage.channel_id)
             .where(ChatMessage.sender_id == user_id, ChatMessage.deleted_at.is_(None),
                    ChatMessage.created_at >= t0, ChatMessage.created_at < t1)
             .order_by(ChatMessage.created_at.desc()).limit(size))
        rows = (await db.execute(q)).all()
        other_ids = {_dm_other(c, user_id) for _, c in rows if c.kind == "dm"} - {None}
        names = dict((await db.execute(select(User.id, User.name).where(User.id.in_(other_ids)))).all()) if other_ids else {}
        for m, c in rows:
            where = (f"Direct message to {names.get(_dm_other(c, user_id), 'someone')}" if c.kind == "dm"
                     else f"#{c.name}" if c.kind == "channel" else (c.name or "Group chat"))
            items.append({"kind": "chat", "at": m.created_at, "title": f"Chat · {where}", "text": m.body,
                          "channel_id": c.id})

    if "attendance" in kinds:
        q = (select(AttendancePunch).where(AttendancePunch.user_id == user_id,
                                           AttendancePunch.punched_at >= t0, AttendancePunch.punched_at < t1)
             .order_by(AttendancePunch.punched_at.desc()).limit(size))
        for p in (await db.scalars(q)).all():
            items.append({"kind": "attendance", "at": p.punched_at,
                          "title": "Checked in" if p.punch_type == "in" else "Checked out", "text": p.notes or ""})

    if "break" in kinds:
        q = (select(Break).where(Break.user_id == user_id, Break.started_at >= t0, Break.started_at < t1)
             .order_by(Break.started_at.desc()).limit(size))
        for b in (await db.scalars(q)).all():
            title = f"Break · {_mins(b.started_at, b.ended_at)}m" if b.ended_at else "On a break now"
            text = f"Until {att.hm(b.ended_at)}. Tracking paused." if b.ended_at else "Tracking paused."
            items.append({"kind": "break", "at": b.started_at, "title": title, "text": text})

    if "idle" in kinds:
        now = datetime.now(timezone.utc)
        warn = cfg().monitoring.idle_warn_minutes
        q = (select(IdlePeriod).where(IdlePeriod.user_id == user_id, IdlePeriod.started_at >= t0,
                                      IdlePeriod.started_at < t1)
             .order_by(IdlePeriod.started_at.desc()).limit(size))
        for i in (await db.scalars(q)).all():
            mins = _mins(i.started_at, i.ended_at or now)
            if mins < warn:  # shorter pauses never show
                continue
            reason = IDLE_REASON.get(i.reason, "")
            title = f"Idle {mins}m" + (f" · reason: {reason}" if reason else "") + ("" if i.ended_at else " (still idle)")
            bits = [f"Ended {att.hm(i.ended_at)}." if i.ended_at else "", i.reason_note,
                    "" if i.reason else "Reason: none given.", "Admins were told." if i.admin_alerted_at else ""]
            items.append({"kind": "idle", "at": i.started_at, "title": title, "text": " ".join(x for x in bits if x)})

    if "screen" in kinds:
        q = (select(ShareEvent).where(ShareEvent.user_id == user_id, ShareEvent.at >= t0, ShareEvent.at < t1)
             .order_by(ShareEvent.at.desc()).limit(size))
        for e in (await db.scalars(q)).all():
            items.append({"kind": "screen", "at": e.at, "title": f"Screen sharing {e.state}",
                          "text": "From the browser extension." if e.source == "extension" else ""})

    items.sort(key=lambda i: i["at"], reverse=True)
    page, next_before = items[:size], None
    if len(page) == size:  # more may exist after this page
        # Items that share the last time may continue on the next page: leave them all for it (`before` is
        # exclusive), unless the whole page has one time (then nothing could ever move forward).
        last = page[-1]["at"]
        trimmed = [i for i in page if i["at"] > last]
        if trimmed:
            page = trimmed
        next_before = page[-1]["at"]
    for i in page:
        i["time"] = att.hm(i["at"])
        i["day"] = att.local_day(i["at"])
    return {"items": page, "next_before": next_before}


def _dm_other(c: ChatChannel, user_id: int) -> int | None:
    """A DM's dm_key is "12:45" (the two ids): the one that isn't this person."""
    try:
        a, b = (int(x) for x in (c.dm_key or "").split(":"))
    except ValueError:
        return None
    return b if a == user_id else a


# ---------- Tasks tab ----------
async def tasks(db: AsyncSession, user_id: int, start: date, end: date) -> list[dict]:
    """Open tasks now, plus the ones finished in the range."""
    check_range(start, end)
    t0, t1 = utc_bounds(start, end)
    q = (select(Task).where(Task.assignee_id == user_id,
                            (Task.status != "done") | and_(Task.completed_at >= t0, Task.completed_at < t1))
         .order_by(Task.status == "done", Task.due_at.asc().nulls_last(), Task.id.desc()).limit(500))  # open tasks + the range: plenty for one screen
    rows = (await db.scalars(q)).all()
    names = dict((await db.execute(select(User.id, User.name))).all())
    now = datetime.now(timezone.utc)
    return [task_out(t, names, now) for t in rows]


# ---------- Audit: an admin opened someone's work page ----------
async def note_view(db: AsyncSession, viewer: User, u: User) -> None:
    """One `work.viewed` row per viewer, per person, per IST day (not one per click). Own page: none."""
    if viewer.id == u.id:
        return
    since = att.to_utc(att.today_local(), "00:00")
    seen = await db.scalar(select(AuditLog.id).where(
        AuditLog.action == "work.viewed", AuditLog.actor_id == viewer.id, AuditLog.entity_type == "user",
        AuditLog.entity_id == str(u.id), AuditLog.at >= since).limit(1))
    if seen:
        return
    audit_service.record(db, actor=viewer, action="work.viewed", entity_type="user", entity_id=u.id,
                         after={"name": u.name})
    await db.commit()
