"""Attendance: check in / out, week view, regularization requests, availability.

Rules:
- A "day" is the IST calendar date. Times are stored in UTC, shown in IST.
- Check-in after shift_start + late_after_minutes (config/app.ini) counts as late.
- Working days are Mon–Sat minus holidays. Punching on other days is allowed (extra work)
  but those days don't count as absent when empty.
- A missed punch is fixed by a regularization request; an approver (attendance.manage)
  accepts it, and the day's times are replaced.
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.ini import cfg
from app.core.errors import AppError
from app.models.attendance import Attendance, Regularization
from app.models.user import AvailabilityLog, User
from app.services import audit_service
from app.services.calendar_service import CalendarService, holiday_set


MAX_SHIFT = timedelta(hours=16)  # longest believable shift for a check-out after midnight


def tz() -> ZoneInfo:
    return ZoneInfo(cfg().app.timezone)


def local_day(at: datetime) -> date:
    return at.astimezone(tz()).date()


def today_local() -> date:
    return local_day(datetime.now(timezone.utc))


def to_utc(day: date, hhmm: str) -> datetime:
    h, m = (int(x) for x in hhmm.split(":"))
    return datetime.combine(day, time(h, m), tz()).astimezone(timezone.utc)


def hm(at: datetime | None) -> str | None:
    return at.astimezone(tz()).strftime("%H:%M") if at else None


def punch_status(check_in_at: datetime) -> str:
    """present or late, from the shift start in config/app.ini."""
    c = cfg().app
    day = local_day(check_in_at)
    late_after = to_utc(day, c.shift_start) + timedelta(minutes=c.late_after_minutes)
    return "late" if check_in_at > late_after else "present"


def hours(a: Attendance | None) -> float:
    if not a or not a.check_in_at or not a.check_out_at:
        return 0.0
    return round((a.check_out_at - a.check_in_at).total_seconds() / 3600, 2)


# ---------- Punching ----------
async def _row(db: AsyncSession, user_id: int, day: date) -> Attendance | None:
    return await db.scalar(select(Attendance).where(Attendance.user_id == user_id, Attendance.day == day))


async def check_in(db: AsyncSession, user: User, now: datetime | None = None) -> Attendance:
    now = now or datetime.now(timezone.utc)
    day = local_day(now)
    row = await _row(db, user.id, day)
    if row and row.check_in_at:
        raise AppError(409, "already_checked_in", f"You already checked in at {hm(row.check_in_at)}.")
    if row is None:
        row = Attendance(user_id=user.id, day=day, source="punch")
        db.add(row)
    row.check_in_at, row.status = now, punch_status(now)
    await db.flush()
    audit_service.record(db, actor=user, action="attendance.check_in", entity_type="attendance",
                         entity_id=row.id, after={"day": day.isoformat(), "at": hm(now), "status": row.status})
    await db.commit()
    return row


async def check_out(db: AsyncSession, user: User, now: datetime | None = None) -> Attendance:
    now = now or datetime.now(timezone.utc)
    row = await _row(db, user.id, local_day(now))
    if row is None or row.check_in_at is None:
        # Working past midnight: the open day is yesterday's (a night shift counts on its start date)
        prev = await _row(db, user.id, local_day(now) - timedelta(days=1))
        # Only a real night shift (started under 16 h ago). A check-in forgotten yesterday must not
        # turn into a 33-hour day: that one is fixed with a regularization request.
        if (prev is not None and prev.check_in_at is not None and prev.check_out_at is None
                and now - prev.check_in_at < MAX_SHIFT):
            row = prev
    if row is None or row.check_in_at is None:
        raise AppError(409, "not_checked_in", "Please check in first.")
    if row.check_out_at:
        raise AppError(409, "already_checked_out", f"You already checked out at {hm(row.check_out_at)}.")
    row.check_out_at = now
    audit_service.record(db, actor=user, action="attendance.check_out", entity_type="attendance",
                         entity_id=row.id, after={"day": row.day.isoformat(), "at": hm(now)})
    await db.commit()
    return row


async def today(db: AsyncSession, user: User, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    day = local_day(now)
    row = await _row(db, user.id, day)
    c = cfg().app
    return {
        "day": day, "check_in": hm(row.check_in_at) if row else None,
        "check_out": hm(row.check_out_at) if row else None,
        "status": row.status if row else None, "hours": hours(row),
        "shift": f"{c.shift_start}–{c.shift_end}", "is_available": user.is_available,
    }


# ---------- Week view ----------
def _day_state(d: date, row: Attendance | None, holidays: set[date], today_: date) -> str:
    if row and row.check_in_at:
        return row.status
    if row and row.status == "leave":
        return "leave"
    if d in holidays:
        return "holiday"
    if d.weekday() == 6:
        return "off"
    return "upcoming" if d >= today_ else "absent"


async def week(db: AsyncSession, user_id: int, week_start: date, now: datetime | None = None) -> dict:
    week_start -= timedelta(days=week_start.weekday())  # always a Monday
    days = [week_start + timedelta(days=i) for i in range(7)]
    rows = {r.day: r for r in (await db.scalars(select(Attendance).where(
        Attendance.user_id == user_id, Attendance.day >= days[0], Attendance.day <= days[-1]))).all()}
    holidays = await holiday_set(db, days[0].year, days[-1].year)
    today_ = local_day(now or datetime.now(timezone.utc))
    out, summary = [], {"present": 0, "late": 0, "leave": 0, "absent": 0, "holiday": 0}
    for d in days:
        row = rows.get(d)
        state = _day_state(d, row, holidays, today_)
        if state in summary:
            summary[state] += 1
        out.append({"day": d, "state": state, "check_in": hm(row.check_in_at) if row else None,
                    "check_out": hm(row.check_out_at) if row else None, "hours": hours(row),
                    "working_day": CalendarService.is_working_day(d, holidays)})
    total = round(sum(x["hours"] for x in out), 2)
    return {"week_start": week_start, "days": out, "summary": summary, "total_hours": total}


# ---------- Availability ----------
async def set_availability(db: AsyncSession, user: User, value: bool) -> bool:
    if user.is_available != value:
        user.is_available = value
        db.add(AvailabilityLog(user_id=user.id, value=value, changed_at=datetime.now(timezone.utc)))
        audit_service.record(db, actor=user, action="user.availability", entity_type="user",
                             entity_id=user.id, after={"is_available": value})
        await db.commit()
    return value


# ---------- Regularization ----------
async def request_regularization(db: AsyncSession, user: User, day: date, check_in: str,
                                 check_out: str | None, reason: str) -> Regularization:
    if day > local_day(datetime.now(timezone.utc)):
        raise AppError(422, "future_day", "You can't regularize a future day.")
    start = to_utc(day, check_in)
    end = to_utc(day, check_out) if check_out else None
    if end and end <= start:
        raise AppError(422, "bad_times", "Check-out must be after check-in.")
    dup = await db.scalar(select(Regularization.id).where(
        Regularization.user_id == user.id, Regularization.day == day, Regularization.status == "pending"))
    if dup:
        raise AppError(409, "duplicate", "You already have a pending request for this day.")
    reg = Regularization(user_id=user.id, day=day, check_in_at=start, check_out_at=end,
                         reason=reason.strip(), status="pending")
    db.add(reg)
    await db.flush()
    audit_service.record(db, actor=user, action="regularization.requested", entity_type="regularization",
                         entity_id=reg.id, after={"day": day.isoformat(), "in": check_in, "out": check_out})
    await db.commit()
    return reg


def reg_out(r: Regularization, name: str) -> dict:
    return {"id": r.id, "user_id": r.user_id, "user_name": name, "day": r.day,
            "check_in": hm(r.check_in_at), "check_out": hm(r.check_out_at), "reason": r.reason,
            "status": r.status, "created_at": r.created_at}


async def list_regularizations(db: AsyncSession, status: str | None = None, user_id: int | None = None) -> list[dict]:
    q = select(Regularization, User.name).join(User, User.id == Regularization.user_id).order_by(Regularization.id.desc())
    if status:
        q = q.where(Regularization.status == status)
    if user_id:
        q = q.where(Regularization.user_id == user_id)
    return [reg_out(r, n) for r, n in (await db.execute(q.limit(200))).all()]


async def decide(db: AsyncSession, approver: User, reg_id: int, approve: bool) -> dict:
    # Locked: if two approvers click at the same moment, the second sees "already decided"
    reg = await db.get(Regularization, reg_id, with_for_update=True, populate_existing=True)
    if reg is None:
        raise AppError(404, "not_found", "Request not found.")
    if reg.status != "pending":
        raise AppError(409, "already_decided", f"This request was already {reg.status}.")
    if reg.user_id == approver.id and approver.role != "admin":
        raise AppError(403, "own_request", "Someone else must approve your own request.")
    reg.status = "approved" if approve else "rejected"
    reg.decided_by, reg.decided_at = approver.id, datetime.now(timezone.utc)
    if approve:
        row = await _row(db, reg.user_id, reg.day)
        before = {"in": hm(row.check_in_at), "out": hm(row.check_out_at)} if row else None
        if row is None:
            row = Attendance(user_id=reg.user_id, day=reg.day)
            db.add(row)
        # A request usually fixes one missed punch ("forgot to check in"); an empty check-out
        # means "keep my real check-out", never "erase it".
        row.check_in_at = reg.check_in_at
        row.check_out_at = reg.check_out_at or row.check_out_at
        if row.check_out_at and row.check_out_at <= row.check_in_at:
            raise AppError(422, "bad_times", "The new check-in is after this person's check-out. "
                                             "Ask them to send both times.")
        row.status, row.source = punch_status(row.check_in_at), "regularized"
        audit_service.record(db, actor=approver, action="attendance.regularized", entity_type="attendance",
                             entity_id=f"{reg.user_id}:{reg.day.isoformat()}", before=before,
                             after={"in": hm(row.check_in_at), "out": hm(row.check_out_at)})
    audit_service.record(db, actor=approver, action=f"regularization.{reg.status}", entity_type="regularization",
                         entity_id=reg.id)
    await db.commit()
    name = await db.scalar(select(User.name).where(User.id == reg.user_id))
    return reg_out(reg, name or "")


# ---------- Team view ----------
async def team_day(db: AsyncSession, day: date) -> list[dict]:
    q = (select(User, Attendance)
         .outerjoin(Attendance, (Attendance.user_id == User.id) & (Attendance.day == day))
         .where(User.status == "active").order_by(User.name))
    holidays = await holiday_set(db, day.year, day.year)
    today_ = local_day(datetime.now(timezone.utc))
    return [{"user_id": u.id, "name": u.name, "is_available": u.is_available,
             "state": _day_state(day, a, holidays, today_), "check_in": hm(a.check_in_at) if a else None,
             "check_out": hm(a.check_out_at) if a else None, "hours": hours(a)}
            for u, a in (await db.execute(q)).all()]
