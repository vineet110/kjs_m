"""Monitoring, Phase B: screenshots, screen sharing on/off, breaks and idle periods.

Rule for everything here: nothing is saved unless the person is checked in. The server checks it, never
trusting the browser. All numbers come from config/monitoring.ini (read with cfg() each time).

Who sends what:
- the portal: screenshots (it holds the screen-share stream), sharing started/stopped/refused, breaks
- the browser extension (Phase C, its own device key): idle started / ended. Until then no idle data comes
  in, and the screens say "Extension not connected".
- the `monitor_watch` job: alerts for long sharing gaps, idle warnings/alerts, breaks left open after
  check-out, and deleting screenshots older than keep_days.

Alerts go to everyone with `monitor.view`, in the portal bell only (no email copy): about 75 people
could otherwise fill the admins' inboxes.
"""
import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.ini import cfg
from app.core.errors import AppError
from app.core.storage import StorageError, storage
from app.jobs.runner import job
from app.models.attendance import Attendance, AttendancePunch
from app.models.monitor import Break, IdlePeriod, Screenshot, ShareEvent
from app.models.notification import Notification
from app.models.user import User
from app.services import attendance_service as att
from app.services import extension_service
from app.services.notification_service import users_with

log = logging.getLogger(__name__)
PREFIX = "screenshots/"  # storage folder; never served by /files, skipped by the off-site backup
JPEG_START = b"\xff\xd8\xff"
IDLE_REASONS = ("call", "meeting", "other")
DEVICES = ("laptop", "phone")
PURGE_BATCH = 500  # screenshots deleted per job run (keeps one run short)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------- Checked in? ----------
async def _today_row(db: AsyncSession, user_id: int, now: datetime) -> Attendance | None:
    return await db.scalar(select(Attendance).where(Attendance.user_id == user_id,
                                                    Attendance.day == att.local_day(now)))


async def is_checked_in(db: AsyncSession, user_id: int, now: datetime | None = None) -> bool:
    """Same rule as attendance `today`: the last punch of today is `in` (old rows without punches:
    checked in and not out)."""
    now = now or _now()
    row = await _today_row(db, user_id, now)
    if not row or not row.check_in_at:
        return False
    last = await db.scalar(select(AttendancePunch.punch_type).where(AttendancePunch.attendance_id == row.id)
                           .order_by(AttendancePunch.punched_at.desc()).limit(1))
    return last == "in" if last else row.check_out_at is None


async def _must_be_in(db: AsyncSession, user: User, now: datetime) -> None:
    if not await is_checked_in(db, user.id, now):
        raise AppError(409, "not_checked_in", "You are not checked in, so nothing is recorded.")


async def open_break(db: AsyncSession, user_id: int) -> Break | None:
    return await db.scalar(select(Break).where(Break.user_id == user_id, Break.ended_at.is_(None)))


async def open_idle(db: AsyncSession, user_id: int) -> IdlePeriod | None:
    return await db.scalar(select(IdlePeriod).where(IdlePeriod.user_id == user_id, IdlePeriod.ended_at.is_(None)))


def _minutes(a: datetime, b: datetime) -> int:
    return max(0, int((b - a).total_seconds() // 60))


async def break_minutes(db: AsyncSession, user_id: int, day: date, now: datetime | None = None) -> int:
    now = now or _now()
    rows = (await db.scalars(select(Break).where(Break.user_id == user_id, Break.day == day))).all()
    return sum(_minutes(b.started_at, b.ended_at or now) for b in rows)


def _alert_admins(db: AsyncSession, admin_ids: list[int], kind: str, title: str, body: str, link: str) -> None:
    """Bell only: email_status "skipped", so the send_emails job never mails these."""
    for uid in set(admin_ids):
        db.add(Notification(user_id=uid, kind=kind, title=title[:200], body=body, link=link, email_status="skipped"))


# ---------- What the portal (and later the extension) needs to know ----------
async def state(db: AsyncSession, user: User, now: datetime | None = None) -> dict:
    now = now or _now()
    c = cfg().monitoring
    checked_in = await is_checked_in(db, user.id, now)
    b = await open_break(db, user.id)
    idle = await open_idle(db, user.id)
    idle_min = _minutes(idle.started_at, now) if idle else 0
    last_shot = await db.scalar(select(func.max(Screenshot.taken_at)).where(Screenshot.user_id == user.id))
    return {
        "checked_in": checked_in,
        "on_break": bool(b),
        "break_started_at": b.started_at if b else None,
        "break_minutes_today": await break_minutes(db, user.id, att.local_day(now), now),
        "extension": await extension_service.is_connected(db, user.id),
        "idle": ({"id": idle.id, "started_at": idle.started_at, "minutes": idle_min, "reason": idle.reason}
                 if idle and idle_min >= c.idle_warn_minutes else None),
        "last_screenshot_at": last_shot,
        "config": {"screenshot_minutes": c.screenshot_minutes, "image_quality": c.image_quality,
                   "max_screenshot_kb": c.max_screenshot_kb, "break_minutes_per_day": c.break_minutes_per_day,
                   "idle_warn_minutes": c.idle_warn_minutes},
    }


# ---------- Device (laptop / phone) ----------
async def set_device(db: AsyncSession, user: User, device: str, now: datetime | None = None) -> None:
    now = now or _now()
    if device not in DEVICES:
        raise AppError(400, "bad_device", "Device must be laptop or phone.")
    await _must_be_in(db, user, now)
    row = await _today_row(db, user.id, now)
    row.device = device
    if device == "phone":
        _alert_admins(db, await users_with(db, "monitor.view"), "monitor.phone",
                      f"{user.name} checked in from a phone", "Nothing is tracked on a phone.",
                      f"/admin/team-work/{user.id}")
    await db.commit()


# ---------- Screenshots ----------
async def save_screenshot(db: AsyncSession, user: User, data: bytes, source: str = "portal",
                          now: datetime | None = None) -> Screenshot:
    now = now or _now()
    c = cfg().monitoring
    await _must_be_in(db, user, now)
    if await open_break(db, user.id):
        raise AppError(409, "on_break", "You are on a break, so no screenshot is taken.")
    if not data.startswith(JPEG_START):
        raise AppError(400, "bad_image", "A screenshot must be a JPEG image.")
    if len(data) > c.max_screenshot_kb * 1024:
        raise AppError(413, "too_big", f"A screenshot may be at most {c.max_screenshot_kb} KB.",
                       {"max_kb": c.max_screenshot_kb})
    # One per interval: a quick second one (a double send, or a page reload) is refused. 80% of the
    # interval, so a slightly early timer in the browser is still fine.
    gap = timedelta(seconds=max(30, c.screenshot_minutes * 60 * 0.8))
    last = await db.scalar(select(func.max(Screenshot.taken_at)).where(Screenshot.user_id == user.id))
    if last and now - last < gap:
        raise AppError(429, "too_soon", "A screenshot was saved a moment ago.")
    key = f"{PREFIX}{user.id}/{att.local_day(now).isoformat()}/{uuid.uuid4().hex}.jpg"
    try:
        storage().put(key, data, "image/jpeg")
    except StorageError as e:
        log.error("monitor.screenshot_store_failed", extra={"reason": str(e)})
        raise AppError(503, "storage_down", "Could not save the screenshot. It will be tried again.") from e
    shot = Screenshot(user_id=user.id, taken_at=now, storage_key=key, size_bytes=len(data), source=source)
    db.add(shot)
    await db.commit()
    return shot


async def screenshots_of(db: AsyncSession, user_id: int, day: date) -> list[dict]:
    t0, t1 = att.to_utc(day, "00:00"), att.to_utc(day + timedelta(days=1), "00:00")
    rows = (await db.scalars(select(Screenshot).where(Screenshot.user_id == user_id, Screenshot.taken_at >= t0,
                                                      Screenshot.taken_at < t1).order_by(Screenshot.taken_at))).all()
    return [{"id": s.id, "taken_at": s.taken_at, "time": att.hm(s.taken_at), "size_kb": round(s.size_bytes / 1024),
             "source": s.source} for s in rows]


async def screenshot_image(db: AsyncSession, user_id: int, shot_id: int) -> bytes:
    """The image bytes, only through the permission-checked route (never a public or /files link)."""
    s = await db.get(Screenshot, shot_id)
    if not s or s.user_id != user_id:
        raise AppError(404, "not_found", "No such screenshot.")
    try:
        return storage().get(s.storage_key)
    except StorageError as e:
        raise AppError(404, "not_found", "This screenshot is no longer stored.") from e


# ---------- Screen sharing on / off ----------
async def share_event(db: AsyncSession, user: User, state_: str, source: str = "portal",
                      now: datetime | None = None) -> None:
    now = now or _now()
    if state_ not in ("started", "stopped", "refused"):
        raise AppError(400, "bad_state", "State must be started, stopped or refused.")
    if not await is_checked_in(db, user.id, now):
        return  # checked out: sharing ending is expected, nothing to record
    db.add(ShareEvent(user_id=user.id, at=now, state=state_, source=source,
                      alerted_at=now if state_ == "refused" else None))
    if state_ == "refused":
        _alert_admins(db, await users_with(db, "monitor.view"), "monitor.share_refused",
                      f"{user.name} refused screen sharing", "The portal still works; no screenshots are taken.",
                      f"/admin/team-work/{user.id}")
    await db.commit()


async def sharing_now(db: AsyncSession, user_id: int, day: date) -> str | None:
    """started | stopped | refused (the last event today), or None (no event today)."""
    t0 = att.to_utc(day, "00:00")
    return await db.scalar(select(ShareEvent.state).where(ShareEvent.user_id == user_id, ShareEvent.at >= t0)
                           .order_by(ShareEvent.at.desc(), ShareEvent.id.desc()).limit(1))


async def share_gaps(db: AsyncSession, user_id: int, day: date) -> list[dict]:
    """Times screen sharing was off (stopped or refused) on a day: [{from, to (None = still off), state}]."""
    t0, t1 = att.to_utc(day, "00:00"), att.to_utc(day + timedelta(days=1), "00:00")
    events = (await db.scalars(select(ShareEvent).where(ShareEvent.user_id == user_id, ShareEvent.at >= t0,
                                                        ShareEvent.at < t1).order_by(ShareEvent.at, ShareEvent.id))).all()
    gaps: list[dict] = []
    for e in events:
        if e.state in ("stopped", "refused") and not (gaps and gaps[-1]["to"] is None):
            gaps.append({"from": att.hm(e.at), "to": None, "state": e.state})
        elif e.state == "started" and gaps and gaps[-1]["to"] is None:
            gaps[-1]["to"] = att.hm(e.at)
    return gaps


# ---------- Breaks ----------
async def start_break(db: AsyncSession, user: User, now: datetime | None = None) -> dict:
    now = now or _now()
    await _must_be_in(db, user, now)
    if await open_break(db, user.id):
        raise AppError(409, "already_on_break", "You are already on a break.")
    db.add(Break(user_id=user.id, day=att.local_day(now), started_at=now))
    idle = await open_idle(db, user.id)
    if idle:  # a break is not idle time
        await _end_idle(db, idle, now)
    try:
        await db.commit()
    except IntegrityError:  # two quick clicks: the other one already started it
        await db.rollback()
        raise AppError(409, "already_on_break", "You are already on a break.")
    return await state(db, user, now)


async def end_break(db: AsyncSession, user: User, now: datetime | None = None) -> dict:
    now = now or _now()
    b = await open_break(db, user.id)
    if not b:
        raise AppError(409, "not_on_break", "You are not on a break.")
    b.ended_at = now
    await _check_break_limit(db, user, b.day, now)
    await db.commit()
    return await state(db, user, now)


async def _check_break_limit(db: AsyncSession, user: User, day: date, now: datetime) -> None:
    limit = cfg().monitoring.break_minutes_per_day
    used = await break_minutes(db, user.id, day, now)
    if used <= limit:
        return
    row = await db.scalar(select(Attendance).where(Attendance.user_id == user.id, Attendance.day == day))
    if not row or row.break_alerted_at:
        return
    row.break_alerted_at = now
    _alert_admins(db, await users_with(db, "monitor.view"), "monitor.break_limit",
                  f"{user.name} has taken {used} minutes of break today", f"The daily limit is {limit} minutes.",
                  f"/admin/team-work/{user.id}")


# ---------- Idle (sent by the browser extension, Phase C) ----------
async def idle_started(db: AsyncSession, user: User, started_at: datetime, now: datetime | None = None) -> None:
    """The extension saw no keyboard or mouse since started_at. Ignored when checked out or on a break."""
    now = now or _now()
    if not await is_checked_in(db, user.id, now) or await open_break(db, user.id) or await open_idle(db, user.id):
        return
    db.add(IdlePeriod(user_id=user.id, started_at=min(started_at, now)))
    try:
        await db.commit()
    except IntegrityError:  # sent twice at once: one open period is enough
        await db.rollback()


async def idle_ended(db: AsyncSession, user: User, ended_at: datetime, now: datetime | None = None) -> None:
    now = now or _now()
    idle = await open_idle(db, user.id)
    if idle:
        await _end_idle(db, idle, min(ended_at, now))
        await db.commit()


async def _end_idle(db: AsyncSession, idle: IdlePeriod, at: datetime) -> None:
    """Shorter than idle_warn_minutes never counts: the row is removed, not kept as a tiny idle period."""
    if _minutes(idle.started_at, at) < cfg().monitoring.idle_warn_minutes:
        await db.delete(idle)
    else:
        idle.ended_at = at


async def set_idle_reason(db: AsyncSession, user: User, idle_id: int, reason: str, note: str = "") -> None:
    if reason not in IDLE_REASONS:
        raise AppError(400, "bad_reason", "Reason must be call, meeting or other.")
    idle = await db.get(IdlePeriod, idle_id)
    if not idle or idle.user_id != user.id:
        raise AppError(404, "not_found", "No such idle period.")
    idle.reason, idle.reason_note = reason, note.strip()[:200]
    await db.commit()


# ---------- The job: alerts and clean-up ----------
@job("monitor_watch", any_time=True, module="monitoring")
async def monitor_watch(db: AsyncSession, now: datetime | None = None) -> dict:
    now = now or _now()
    c = cfg().monitoring
    admins = await users_with(db, "monitor.view")
    names = dict((await db.execute(select(User.id, User.name))).all())
    out = {"gaps": 0, "idle_warned": 0, "idle_alerted": 0, "breaks_closed": 0, "screenshots_deleted": 0}

    # 1. Sharing stopped and not started again within gap_alert_minutes, while still checked in: tell admins once
    stops = (await db.scalars(select(ShareEvent).where(
        ShareEvent.state == "stopped", ShareEvent.alerted_at.is_(None),
        ShareEvent.at <= now - timedelta(minutes=c.gap_alert_minutes)))).all()
    for e in stops:
        restarted = await db.scalar(select(ShareEvent.id).where(
            ShareEvent.user_id == e.user_id, ShareEvent.state == "started", ShareEvent.at > e.at).limit(1))
        e.alerted_at = now  # handled either way: never looked at again
        if restarted or not await is_checked_in(db, e.user_id, now):
            continue
        _alert_admins(db, admins, "monitor.share_gap",
                      f"{names.get(e.user_id, 'Someone')}: screen sharing off since {att.hm(e.at)}",
                      "Screen sharing stopped while checked in.", f"/admin/team-work/{e.user_id}")
        out["gaps"] += 1

    # 2. Idle: warned once (the portal and the extension show the warning), admins told once
    for idle in (await db.scalars(select(IdlePeriod).where(IdlePeriod.ended_at.is_(None)))).all():
        if not await is_checked_in(db, idle.user_id, now):  # checked out while idle: close it
            await _end_idle(db, idle, now)
            continue
        mins = _minutes(idle.started_at, now)
        if mins >= c.idle_warn_minutes and not idle.warned_at:
            idle.warned_at = now
            out["idle_warned"] += 1
        if mins >= c.idle_admin_minutes and not idle.admin_alerted_at:
            idle.admin_alerted_at = now
            reason = f" Reason given: {idle.reason}." if idle.reason else " No reason given."
            _alert_admins(db, admins, "monitor.idle", f"{names.get(idle.user_id, 'Someone')} has been idle for {mins} minutes",
                          f"Idle since {att.hm(idle.started_at)}.{reason}", f"/admin/team-work/{idle.user_id}")
            out["idle_alerted"] += 1

    # 3. A break left open after check-out ends at check-out (or now)
    for b in (await db.scalars(select(Break).where(Break.ended_at.is_(None)))).all():
        if not await is_checked_in(db, b.user_id, now):
            row = await db.scalar(select(Attendance).where(Attendance.user_id == b.user_id, Attendance.day == b.day))
            b.ended_at = max(b.started_at, (row.check_out_at if row and row.check_out_at else now))
            out["breaks_closed"] += 1

    # 4. Screenshots older than keep_days: the file first, then the row (a failed delete is tried again next run)
    old = (await db.scalars(select(Screenshot).where(Screenshot.taken_at < now - timedelta(days=c.keep_days))
                            .order_by(Screenshot.taken_at).limit(PURGE_BATCH))).all()
    gone = []
    for s in old:
        try:
            storage().delete(s.storage_key)
            gone.append(s.id)
        except StorageError:
            log.warning("monitor.screenshot_delete_failed", extra={"screenshot_id": s.id})
    if gone:
        await db.execute(delete(Screenshot).where(Screenshot.id.in_(gone)))
    out["screenshots_deleted"] = len(gone)
    return out
