"""The attendance feed for the laptop-monitoring server (INTEGRATION_PLAN.md, Phase 1).

How the monitoring server reads events (monitering/backend/app/services/crm_sync.py apply_changes):
- each event id is applied once, sorted by `at`, and never edited afterwards;
- punch_in opens a session only if none is open; punch_out closes the open one.
So per person the events here must ALWAYS alternate punch_in -> punch_out, with `at` going forward.
Every write goes through _write(), which holds a per-person lock and checks the last event.

Three things keep it in step with real life:
1. check-in / check-out write an event in the same transaction as the punch;
2. a forgotten check-out: the `monitoring_auto_out` job ends it at shift end + grace (and check_in closes an
   open one first), so the laptop is not tracked all night and does not lock the next morning;
3. a regularization only sends a check-out that closes a day still open here. Moving a time that was
   already sent is not sent: the monitoring server cannot take a correction (it would make a ghost session).

No waiting: the moment a transaction that wrote events (or changed a person) commits, `_after_commit`
starts a push to the monitoring server (POST /api/crm/attendance/push, /api/crm/employees/push). The push
sends each person's recent events in order, read after the commit, so two pushes arriving in either order
give the same result (monitoring applies each id once). The 30 s poll stays only as a safety net.
"""
import asyncio
import logging
import re
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import delete, event, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.config.ini import cfg
from app.core.database import AsyncSessionLocal
from app.core.errors import AppError
from app.core.modules import running
from app.jobs.runner import job
from app.models.monitoring_link import AttendanceEvent
from app.models.shift import Shift
from app.models.user import User
from app.services import notification_service

log = logging.getLogger(__name__)

IN, OUT = "punch_in", "punch_out"
LOCK_SPACE = 7337  # pg_advisory_xact_lock(LOCK_SPACE, user_id): one writer per person at a time
ONE_SECOND = timedelta(seconds=1)
# Security limits (in code on purpose, not in an ini): how much one feed request may read
MAX_EVENTS_RANGE = timedelta(days=31)  # longer asks are shortened to their last 31 days (only the end matters)


def _tz() -> ZoneInfo:
    return ZoneInfo(cfg().app.timezone)


def _iso(at: datetime) -> str:
    return at.astimezone(timezone.utc).isoformat()  # always with an offset: monitoring refuses naive times


# ---------- Writing (one rule: in, out, in, out) ----------
async def _lock(db: AsyncSession, user_id: int) -> None:
    await db.execute(text("SELECT pg_advisory_xact_lock(:space, :uid)"), {"space": LOCK_SPACE, "uid": user_id})


async def last_event(db: AsyncSession, user_id: int) -> AttendanceEvent | None:
    return await db.scalar(select(AttendanceEvent).where(AttendanceEvent.user_id == user_id)
                           .order_by(AttendanceEvent.at.desc(), AttendanceEvent.id.desc()).limit(1))


def _add(db: AsyncSession, user_id: int, event: str, at: datetime, source: str, ref: str = "") -> AttendanceEvent:
    ev = AttendanceEvent(user_id=user_id, event=event, at=at, source=source, ref=ref)
    db.add(ev)
    return ev


async def on_check_in(db: AsyncSession, user_id: int, now: datetime) -> None:
    """Called by attendance_service.check_in, inside its transaction."""
    await _lock(db, user_id)
    last = await last_event(db, user_id)
    if last is not None and last.event == IN:
        # The last session was never closed (auto-out didn't run: jobs off, server down). Close it first,
        # or the monitoring server ignores this check-in and keeps the old session open. Same time the
        # auto-out job would have used, so a forgotten check-out never becomes a 16-hour day.
        close_at = auto_out_at(last.at, await _shift_of(db, user_id))
        _add(db, user_id, OUT, max(last.at + ONE_SECOND, min(now - ONE_SECOND, close_at)), "auto", "before_check_in")
    at = now if last is None else max(now, last.at + 2 * ONE_SECOND)
    _add(db, user_id, IN, at, "punch")
    await db.flush()


async def on_check_out(db: AsyncSession, user_id: int, now: datetime) -> None:
    """Called by attendance_service.check_out, inside its transaction."""
    await _lock(db, user_id)
    last = await last_event(db, user_id)
    if last is None or last.event == OUT:
        return  # already closed here (auto-out came first), or opened before the feed existed
    _add(db, user_id, OUT, max(now, last.at + ONE_SECOND), "punch")
    await db.flush()


async def on_regularization(db: AsyncSession, user_id: int, day: date, check_out_at: datetime | None,
                            reg_id: int, now: datetime | None = None) -> None:
    """Called when a regularization is approved. Sends only "close the day that is still open here"."""
    now = now or datetime.now(timezone.utc)
    if check_out_at is None or check_out_at > now:
        return
    await _lock(db, user_id)
    last = await last_event(db, user_id)
    if last is None or last.event != IN or check_out_at <= last.at:
        return
    if shift_day(last.at, await _shift_of(db, user_id)) != day:
        return
    _add(db, user_id, OUT, check_out_at, "regularization", f"reg:{reg_id}")
    await db.flush()


# ---------- Forgotten check-outs ----------
def _is_night(shift: Shift | None) -> bool:
    return shift is not None and (shift.is_night_shift or shift.end_time <= shift.start_time)


def shift_day(at: datetime, shift: Shift | None) -> date:
    """The day the shift started: a night-shift check-in at 00:30 (before the shift's end time) belongs to the
    shift that began the evening before (the same day the CRM gives a regularization of that shift)."""
    local = at.astimezone(_tz())
    if _is_night(shift) and local.time() < shift.end_time:
        return local.date() - timedelta(days=1)
    return local.date()


async def _shift_of(db: AsyncSession, user_id: int) -> Shift | None:
    shift_id = await db.scalar(select(User.shift_id).where(User.id == user_id))
    return await db.get(Shift, shift_id) if shift_id else None


def _shift_end(day: date, shift: Shift | None) -> datetime:
    """When the shift that started on `day` ends (a night shift ends the next day)."""
    if shift is not None:
        end_day = day + timedelta(days=1) if _is_night(shift) else day
        return datetime.combine(end_day, shift.end_time, _tz()).astimezone(timezone.utc)
    h, m = (int(x) for x in cfg().app.shift_end.split(":"))
    return datetime.combine(day, time(h, m), _tz()).astimezone(timezone.utc)


def auto_out_at(last_in: datetime, shift: Shift | None) -> datetime:
    """When an open check-in is closed for monitoring: shift end + grace; for a check-in after the shift ended
    (overtime, or evening work with no shift), check-in + overtime_auto_out_hours. Never later than
    max_shift_hours after the check-in."""
    c = cfg().monitoring_link
    end = _shift_end(shift_day(last_in, shift), shift)
    if last_in < end:
        planned = end + timedelta(minutes=c.auto_out_grace_minutes)
    else:
        planned = last_in + timedelta(hours=c.overtime_auto_out_hours)
    return max(last_in + ONE_SECOND, min(planned, last_in + timedelta(hours=cfg().attendance.max_shift_hours)))


def _window() -> timedelta:
    """Every open check-in is younger than this (auto-out closes it within max_shift_hours)."""
    return timedelta(hours=cfg().attendance.max_shift_hours + 1)


async def _db_now(db: AsyncSession) -> datetime:
    """The database's clock: the same clock that stamps created_at (the feed cursor), so the app's own clock
    running ahead or behind can never make the feed skip rows."""
    return await db.scalar(text("SELECT clock_timestamp()"))


async def _open_check_ins(db: AsyncSession, since: datetime | None = None) -> list[tuple[int, int, datetime]]:
    """(event id, user id, at) of each person whose last event is a check-in (a later event would also be in
    the window, so the window loses nothing). Plain values: auto_out commits per person, and a committed ORM
    row would reload itself (not allowed in async code)."""
    since = since or (await _db_now(db)) - _window()
    latest = (select(AttendanceEvent)
              .where(AttendanceEvent.at > since)
              .distinct(AttendanceEvent.user_id)
              .order_by(AttendanceEvent.user_id, AttendanceEvent.at.desc(), AttendanceEvent.id.desc())
              .subquery())
    rows = await db.execute(select(latest.c.id).where(latest.c.event == IN))
    ids = [r[0] for r in rows]
    if not ids:
        return []
    found = await db.execute(select(AttendanceEvent.id, AttendanceEvent.user_id, AttendanceEvent.at)
                             .where(AttendanceEvent.id.in_(ids)))
    return [(r.id, r.user_id, r.at) for r in found]


@job("monitoring_auto_out", any_time=True, module="monitoring")
async def auto_out(db: AsyncSession, now: datetime | None = None) -> dict:
    """Close check-ins left open past shift end + grace. CRM attendance is not changed (the person still
    sends a missed-punch request); only monitoring stops.
    One commit per person: one long transaction would hold everyone's lock (their check-ins wait) and save
    rows the feed has already read past. Safe to run again: each person is re-checked under their lock."""
    now = now or datetime.now(timezone.utc)
    closed = 0
    for ev_id, user_id, last_in in await _open_check_ins(db, now - _window()):
        at = auto_out_at(last_in, await _shift_of(db, user_id))
        if at > now:
            continue
        await _lock(db, user_id)
        last = await last_event(db, user_id)
        if last is None or last.id != ev_id:
            await db.commit()  # they checked out (or in again) since we looked: just let go of the lock
            continue
        _add(db, user_id, OUT, at, "auto", "shift_end")
        local = at.astimezone(_tz()).strftime("%H:%M")
        notification_service.notify(
            db, [user_id], "monitoring.auto_out", f"Laptop monitoring stopped at {local}",
            "You did not check out. If you were still working, send a missed-punch request.", "/employee/attendance")
        await db.commit()
        closed += 1
    return {"closed": closed}


# No portal area on purpose: punches write events even while `monitoring` is off (so the feed is right the
# day it is switched on), so the clean-up must run then too.
@job("monitoring_events_purge", any_time=True)
async def purge_events(db: AsyncSession, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    keep = timedelta(days=cfg().monitoring_link.keep_events_days)
    purged = (await db.execute(delete(AttendanceEvent).where(AttendanceEvent.created_at < now - keep))).rowcount
    await db.commit()
    return {"purged": purged or 0}


# ---------- Reading (the feed) ----------
def _out(ev: AttendanceEvent) -> dict:
    return {"id": str(ev.id), "employee_id": str(ev.user_id), "event": ev.event, "at": _iso(ev.at),
            "break_type": None}


async def changes(db: AsyncSession, since: datetime, now: datetime | None = None) -> dict:
    """Events written since `since` (read back feed_overlap_seconds: repeats are fine, the monitoring server
    applies each id once). `server_time` is the next `since`."""
    if since.tzinfo is None:
        raise AppError(422, "naive_time", "`since` needs a time zone offset.")
    now = now or await _db_now(db)
    c = cfg().monitoring_link
    rows = list((await db.scalars(
        select(AttendanceEvent)
        .where(AttendanceEvent.created_at >= since - timedelta(seconds=c.feed_overlap_seconds))
        .order_by(AttendanceEvent.created_at, AttendanceEvent.id)
        .limit(c.feed_max_rows + 1))).all())
    server_time = now
    if len(rows) > c.feed_max_rows:
        # More than one page: catching up. Cut the page after a whole created_at group (rows written in one
        # transaction share it). The next poll starts at the EARLIER of:
        # - just after that group: old rows move strictly forward (a group bigger than a page can't come back
        #   on every poll for ever);
        # - now - overlap: recent rows keep the full overlap (a slow transaction may still be committing).
        overlap = timedelta(seconds=c.feed_overlap_seconds)
        last_ct = rows[c.feed_max_rows - 1].created_at
        rows = [e for e in rows if e.created_at < last_ct] + list((await db.scalars(
            select(AttendanceEvent).where(AttendanceEvent.created_at == last_ct).order_by(AttendanceEvent.id))).all())
        server_time = min(last_ct + timedelta(microseconds=1), now - overlap) + overlap  # we take it off again
    # Also every check-in still open, by its own id: a no-op for the monitoring server when it has it already,
    # but a server that starts (or is switched on) later still learns who is at work right now.
    seen = {e.id for e in rows}
    open_ids = [ev_id for ev_id, _, _ in await _open_check_ins(db, now - _window()) if ev_id not in seen]
    if open_ids:
        rows += list((await db.scalars(select(AttendanceEvent).where(AttendanceEvent.id.in_(open_ids))
                                       .order_by(AttendanceEvent.at, AttendanceEvent.id))).all())
    return {"server_time": _iso(server_time), "changes": [_out(e) for e in rows]}


async def events_for(db: AsyncSession, employee_id: str, start: datetime, end: datetime) -> dict:
    if start.tzinfo is None or end.tzinfo is None:
        raise AppError(422, "naive_time", "`from` and `to` need a time zone offset.")
    if end < start:
        raise AppError(422, "bad_range", "`to` must be after `from`.")
    # A laptop closed through a long leave asks for more than 31 days: answer its last 31 days (the lock
    # decision only needs the recent end). Refusing it would look like "CRM down" to the monitoring server.
    start = max(start, end - MAX_EVENTS_RANGE)
    if not re.fullmatch(r"[0-9]{1,9}", employee_id):  # ASCII digits that fit users.id (isdigit takes "²")
        raise AppError(422, "bad_employee_id", "Unknown employee id.")
    rows = (await db.scalars(
        select(AttendanceEvent)
        .where(AttendanceEvent.user_id == int(employee_id), AttendanceEvent.at >= start, AttendanceEvent.at <= end)
        .order_by(AttendanceEvent.at, AttendanceEvent.id))).all()
    return {"changes": [_out(e) for e in rows]}


LISTED = ("active", "disabled")  # pending and rejected sign-ups never worked here: not listed


def _employee_out(u: User) -> dict:
    # "disabled" is sent as it is: the monitoring server revokes laptops only for "exited" (someone who left),
    # so a suspension that is switched back on keeps its laptop. A disabled person can't punch in anyway.
    return {"employee_id": str(u.id), "name": u.name, "email": u.email, "department": u.branch or None,
            "manager_id": str(u.reporting_to) if u.reporting_to else None, "backup_approver_id": None,
            "status": u.status}


async def employees(db: AsyncSession) -> dict:
    rows = (await db.scalars(select(User).where(User.status.in_(LISTED)).order_by(User.id))).all()
    return {"employees": [_employee_out(u) for u in rows]}


# ---------- Push: tell the monitoring server the moment something is saved ----------
# What the monitoring server needs to know about a person (any other column changing is not pushed)
EMPLOYEE_FIELDS = ("name", "email", "branch", "reporting_to", "status")
_PENDING_EVENTS, _PENDING_PEOPLE = "monitoring_push_events", "monitoring_push_people"
_tasks: set[asyncio.Task] = set()  # running pushes (a task nobody holds can be garbage-collected mid-way)
_client: httpx.AsyncClient | None = None


def push_configured() -> bool:
    return bool(settings.MONITORING_BASE_URL and settings.MONITORING_API_KEY) and running("monitoring")


def http() -> httpx.AsyncClient:
    """One client for the whole process: its connection stays open, so a push doesn't pay for a new one."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(base_url=settings.MONITORING_BASE_URL.rstrip("/"),
                                    headers={"X-Api-Key": settings.MONITORING_API_KEY})
    return _client


@event.listens_for(Session, "after_flush")
def _collect(session: Session, _ctx) -> None:
    """Note who changed in this transaction (the lists are still pre-flush here; history is still there)."""
    for obj in list(session.new) + list(session.dirty):
        if isinstance(obj, AttendanceEvent) and obj in session.new:
            session.info.setdefault(_PENDING_EVENTS, set()).add(obj.user_id)
        elif isinstance(obj, User):
            state = inspect(obj)
            if obj in session.new or any(state.attrs[f].history.has_changes() for f in EMPLOYEE_FIELDS):
                session.info.setdefault(_PENDING_PEOPLE, set()).add(obj.id)


@event.listens_for(Session, "after_commit")
def _after_commit(session: Session) -> None:
    people_events = session.info.pop(_PENDING_EVENTS, set())
    people = session.info.pop(_PENDING_PEOPLE, set())
    if not (people_events or people) or not push_configured():
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # a script without an event loop (seed, alembic): the poll catches up
        return
    task = loop.create_task(push(people_events, people))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


@event.listens_for(Session, "after_rollback")
def _forget(session: Session) -> None:
    session.info.pop(_PENDING_EVENTS, None)
    session.info.pop(_PENDING_PEOPLE, None)


async def push(people_events: set[int], people: set[int]) -> None:
    """Runs right after the commit, in its own session (so it reads only committed rows). Never raises: a
    failed push is logged and the monitoring server's poll picks the change up."""
    try:
        async with AsyncSessionLocal() as db:
            if people:
                rows = (await db.scalars(select(User).where(User.id.in_(people), User.status.in_(LISTED)))).all()
                if rows:
                    await _post("/api/crm/employees/push", {"employees": [_employee_out(u) for u in rows]})
            if people_events:
                since = (await _db_now(db)) - _window()
                evs = (await db.scalars(select(AttendanceEvent)
                                        .where(AttendanceEvent.user_id.in_(people_events), AttendanceEvent.at > since)
                                        .order_by(AttendanceEvent.at, AttendanceEvent.id))).all()
                if evs:
                    await _post("/api/crm/attendance/push", {"changes": [_out(e) for e in evs]})
    except Exception:
        log.exception("monitoring.push_failed")


async def _post(path: str, body: dict) -> None:
    r = await http().post(path, json=body, timeout=cfg().monitoring_link.push_timeout_seconds)
    if r.status_code >= 400:
        log.warning("monitoring.push_refused", extra={"path": path, "status": r.status_code})


async def wait_for_pushes() -> None:
    """Tests: wait until every push started so far has finished."""
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)
