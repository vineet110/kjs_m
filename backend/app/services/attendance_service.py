"""Attendance: check in / out, week/month views, regularization requests, availability, and export."""
import asyncio
import calendar
import io
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.ini import cfg
from app.core.errors import AppError
from app.models.attendance import Attendance, Regularization
from app.models.shift import Shift
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
    """Attendance is marked 'present' on punch (late penalty and grace periods removed)."""
    return "present"


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
    if row:
        if row.check_out_at:
            raise AppError(409, "shift_completed", f"You already completed your shift today (checked out at {hm(row.check_out_at)}).")
        if row.status == "leave":
            raise AppError(409, "on_leave", "You have an approved leave for today.")
        if row.check_in_at:
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


async def check_out(db: AsyncSession, user: User, now: datetime | None = None, notes: str | None = None) -> Attendance:
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
                         entity_id=row.id, after={"day": row.day.isoformat(), "at": hm(now), "notes": notes})
    await db.commit()
    return row


async def today(db: AsyncSession, user: User, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    day = local_day(now)
    row = await _row(db, user.id, day)
    c = cfg().app
    shift_str = f"{c.shift_start}–{c.shift_end}"
    shift_name = "General Shift"
    shift_code = "GEN"
    if user.shift_id:
        shift = await db.get(Shift, user.shift_id)
        if shift:
            shift_str = f"{shift.start_time.strftime('%H:%M')}–{shift.end_time.strftime('%H:%M')}"
            shift_name = shift.name
            shift_code = shift.code
    return {
        "day": day, "check_in": hm(row.check_in_at) if row else None,
        "check_out": hm(row.check_out_at) if row else None,
        "status": row.status if row else None, "hours": hours(row),
        "shift": shift_str, "shift_name": shift_name, "shift_code": shift_code,
        "is_available": user.is_available,
    }


# ---------- Week view ----------
def _day_state(d: date, row: Attendance | None, holidays: set[date], today_: date, joined_on: date | None = None) -> str:
    if row and row.check_in_at:
        return row.status
    if row and row.status in ("leave", "half_day"):
        return row.status
    if d in holidays:
        return "holiday"
    if d.weekday() == 6:
        return "off"
    if joined_on and d < joined_on:
        return "not_joined"
    return "upcoming" if d >= today_ else "absent"


async def week(db: AsyncSession, user_id: int, week_start: date, now: datetime | None = None) -> dict:
    week_start -= timedelta(days=week_start.weekday())  # always a Monday
    days = [week_start + timedelta(days=i) for i in range(7)]
    target_user = await db.get(User, user_id)
    joined_on = target_user.joined_on if target_user else None
    rows = {r.day: r for r in (await db.scalars(select(Attendance).where(
        Attendance.user_id == user_id, Attendance.day >= days[0], Attendance.day <= days[-1]))).all()}
    holidays = await holiday_set(db, days[0].year, days[-1].year)
    today_ = local_day(now or datetime.now(timezone.utc))
    out, summary = [], {"present": 0, "leave": 0, "absent": 0, "holiday": 0, "not_joined": 0}
    for d in days:
        row = rows.get(d)
        state = _day_state(d, row, holidays, today_, joined_on)
        if state in summary:
            summary[state] += 1
        out.append({"day": d, "state": state, "check_in": hm(row.check_in_at) if row else None,
                    "check_out": hm(row.check_out_at) if row else None, "hours": hours(row),
                    "working_day": CalendarService.is_working_day(d, holidays)})
    total = round(sum(x["hours"] for x in out), 2)
    return {"week_start": week_start, "days": out, "summary": summary, "total_hours": total}
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
             "state": _day_state(day, a, holidays, today_, u.joined_on), "check_in": hm(a.check_in_at) if a else None,
             "check_out": hm(a.check_out_at) if a else None, "hours": hours(a)}
            for u, a in (await db.execute(q)).all()]


# ---------- Month View (Zoho-Style Calendar Grid) ----------
async def month(db: AsyncSession, user_id: int, year: int, month_num: int, now: datetime | None = None) -> dict:
    if not (1 <= month_num <= 12):
        raise AppError(422, "bad_month", "Month must be between 1 and 12.")
    if not (2000 <= year <= 2100):
        raise AppError(422, "bad_year", "Year must be between 2000 and 2100.")

    _, num_days = calendar.monthrange(year, month_num)
    start_date = date(year, month_num, 1)
    end_date = date(year, month_num, num_days)

    target_user = await db.get(User, user_id)
    joined_on = target_user.joined_on if target_user else None
    shift_name = "General Shift"
    shift_str = "09:30–18:30"
    shift_code = "GEN"
    if target_user and target_user.shift_id:
        shift = await db.get(Shift, target_user.shift_id)
        if shift:
            shift_name = shift.name
            shift_str = f"{shift.start_time.strftime('%H:%M')}–{shift.end_time.strftime('%H:%M')}"
            shift_code = shift.code

    rows = {r.day: r for r in (await db.scalars(select(Attendance).where(
        Attendance.user_id == user_id, Attendance.day >= start_date, Attendance.day <= end_date))).all()}
    holidays = await holiday_set(db, year, year)
    today_ = local_day(now or datetime.now(timezone.utc))

    days_out = []
    summary = {"present": 0, "leave": 0, "absent": 0, "holiday": 0, "off": 0, "not_joined": 0, "upcoming": 0}
    working_days_count = 0

    for day_i in range(1, num_days + 1):
        cur_date = date(year, month_num, day_i)
        is_working = CalendarService.is_working_day(cur_date, holidays)
        if is_working:
            working_days_count += 1

        row = rows.get(cur_date)
        state = _day_state(cur_date, row, holidays, today_, joined_on)
        if state in summary:
            summary[state] += 1

        days_out.append({
            "day": cur_date.isoformat(),
            "day_num": day_i,
            "weekday": cur_date.weekday(),  # 0=Mon..6=Sun
            "state": state,
            "check_in": hm(row.check_in_at) if row else None,
            "check_out": hm(row.check_out_at) if row else None,
            "hours": hours(row),
            "working_day": is_working,
            "source": row.source if row else None,
        })

    total_hours = round(sum(d["hours"] for d in days_out), 2)
    return {
        "year": year,
        "month": month_num,
        "month_name": calendar.month_name[month_num],
        "user_id": user_id,
        "user_name": target_user.name if target_user else "",
        "shift": {"name": shift_name, "code": shift_code, "hours": shift_str},
        "days": days_out,
        "summary": summary,
        "total_hours": total_hours,
        "working_days": working_days_count,
    }


# ---------- Excel Export (Admin Reports) ----------
MAX_EXPORT_DAYS = 366


def _build_excel_workbook(
    users: list[User],
    shifts: dict[int, Shift],
    att_rows: dict[tuple[int, date], Attendance],
    holidays: set[date],
    start_date: date,
    end_date: date,
    today_: date,
    status_filter: str | None,
) -> io.BytesIO:
    wb = Workbook()
    ws_detail = wb.active
    ws_detail.title = "Detailed Attendance"

    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")
    border_thin = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0"),
    )

    headers = [
        "Emp ID", "Employee Name", "Email", "Date", "Day",
        "Shift", "Check In", "Check Out", "Hours Worked", "Status", "Source"
    ]
    ws_detail.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws_detail.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align_center

    # User summary aggregation
    emp_summary = {}

    cur_row = 2
    for u in users:
        emp_summary[u.id] = {
            "name": u.name,
            "email": u.email,
            "present_days": 0,
            "leave_days": 0,
            "absent_days": 0,
            "total_hours": 0.0,
        }
        shift = shifts.get(u.shift_id) if u.shift_id else None
        shift_label = shift.name if shift else "General Shift"

        d = start_date
        while d <= end_date:
            row = att_rows.get((u.id, d))
            state = _day_state(d, row, holidays, today_, u.joined_on)

            if status_filter and state.lower() != status_filter.lower():
                d += timedelta(days=1)
                continue

            h = hours(row) if row else 0.0
            if state == "present":
                emp_summary[u.id]["present_days"] += 1
                emp_summary[u.id]["total_hours"] += h
            elif state == "leave":
                emp_summary[u.id]["leave_days"] += 1
            elif state == "absent":
                emp_summary[u.id]["absent_days"] += 1

            ws_detail.append([
                u.id,
                u.name,
                u.email,
                d.strftime("%Y-%m-%d"),
                d.strftime("%A"),
                shift_label,
                hm(row.check_in_at) if row else "—",
                hm(row.check_out_at) if row else "—",
                h if h > 0 else "—",
                state.replace("_", " ").title(),
                (row.source.title() if row and row.source else "—"),
            ])
            for col_idx in range(1, len(headers) + 1):
                c = ws_detail.cell(row=cur_row, column=col_idx)
                c.border = border_thin
                c.alignment = align_left if col_idx in (2, 3) else align_center
            cur_row += 1
            d += timedelta(days=1)

    # Auto-adjust column widths
    for col in ws_detail.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_detail.column_dimensions[col_letter].width = max(max_len + 3, 12)

    # 5. Sheet 2: Employee Summary Matrix
    ws_sum = wb.create_sheet(title="Employee Summary")
    sum_headers = ["Emp ID", "Employee Name", "Email", "Days Present", "Days on Leave", "Days Absent", "Total Hours", "Avg Hours/Day"]
    ws_sum.append(sum_headers)
    for col_idx in range(1, len(sum_headers) + 1):
        cell = ws_sum.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align_center

    s_row = 2
    for uid, s in emp_summary.items():
        avg_h = round(s["total_hours"] / s["present_days"], 2) if s["present_days"] > 0 else 0.0
        ws_sum.append([
            uid,
            s["name"],
            s["email"],
            s["present_days"],
            s["leave_days"],
            s["absent_days"],
            round(s["total_hours"], 2),
            avg_h,
        ])
        for col_idx in range(1, len(sum_headers) + 1):
            c = ws_sum.cell(row=s_row, column=col_idx)
            c.border = border_thin
            c.alignment = align_left if col_idx in (2, 3) else align_center
        s_row += 1

    for col in ws_sum.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_sum.column_dimensions[col_letter].width = max(max_len + 3, 14)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


async def export_excel(
    db: AsyncSession,
    start_date: date,
    end_date: date,
    user_id: int | None = None,
    status_filter: str | None = None,
) -> io.BytesIO:
    if end_date < start_date:
        raise AppError(422, "bad_dates", "End date cannot be earlier than start date.")
    if (end_date - start_date).days > MAX_EXPORT_DAYS:
        raise AppError(422, "range_too_large", f"Date range cannot exceed {MAX_EXPORT_DAYS} days.")

    # 1. Fetch users
    uq = select(User).where(User.status == "active").order_by(User.name)
    if user_id:
        uq = uq.where(User.id == user_id)
    users = list((await db.scalars(uq)).all())
    if not users:
        raise AppError(404, "no_users", "No matching employees found.")

    # 2. Fetch shifts
    shifts = {s.id: s for s in (await db.scalars(select(Shift))).all()}

    # 3. Fetch attendance
    aq = select(Attendance).where(Attendance.day >= start_date, Attendance.day <= end_date)
    if user_id:
        aq = aq.where(Attendance.user_id == user_id)
    att_rows = {(r.user_id, r.day): r for r in (await db.scalars(aq)).all()}

    # 4. Holidays
    holidays = await holiday_set(db, start_date.year, end_date.year)
    today_ = today_local()

    return await asyncio.to_thread(
        _build_excel_workbook,
        users,
        shifts,
        att_rows,
        holidays,
        start_date,
        end_date,
        today_,
        status_filter,
    )
