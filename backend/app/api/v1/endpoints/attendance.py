"""Attendance, availability, shifts, leaves, and reports. Own data: any logged-in staff member.
Team views and approvals: the `attendance.manage` permission."""
from datetime import date, time
import urllib.parse

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import current_user, require_permission
from app.models.user import User
from app.services import attendance_service as svc
from app.services import calendar_service
from app.services import leave_service
from app.services import shift_service

router = APIRouter()
HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"


@router.get("/today")
async def today(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await svc.today(db, user)


@router.post("/check-in")
async def check_in(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await svc.check_in(db, user)
    return await svc.today(db, user)


class CheckOutIn(BaseModel):
    notes: str | None = None


@router.post("/check-out")
async def check_out(data: CheckOutIn | None = None, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    notes = data.notes if data else None
    await svc.check_out(db, user, notes=notes)
    return await svc.today(db, user)


@router.get("/week")
async def my_week(start: date | None = None, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await svc.week(db, user.id, start or svc.today_local())


@router.get("/month")
async def my_month(
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db)
):
    today_ = svc.today_local()
    return await svc.month(db, user.id, year or today_.year, month or today_.month)


@router.get("/holidays")
async def holidays(
    year: int | None = Query(default=None, ge=2000, le=2100),
    _: User = Depends(current_user),
    db: AsyncSession = Depends(get_db)
):
    rows = await calendar_service.list_holidays(db, year or svc.today_local().year)
    return [{"id": h.id, "day": h.day, "name": h.name} for h in rows]


class AvailabilityIn(BaseModel):
    available: bool


@router.post("/availability")
async def availability(data: AvailabilityIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return {"is_available": await svc.set_availability(db, user, data.available)}


# ---------- Missed Punch (Regularization) ----------
class RegularizeIn(BaseModel):
    day: date
    check_in: str = Field(pattern=HHMM)
    check_out: str | None = Field(default=None, pattern=HHMM)
    reason: str = Field(min_length=3, max_length=500)


@router.post("/regularizations", status_code=201)
async def request_regularization(data: RegularizeIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    reg = await svc.request_regularization(db, user, data.day, data.check_in, data.check_out, data.reason)
    return svc.reg_out(reg, user.name)


@router.get("/regularizations")
async def my_regularizations(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await svc.list_regularizations(db, user_id=user.id)


# ---------- Leave Management ----------
class LeaveRequestIn(BaseModel):
    leave_type: str = Field(min_length=2, max_length=30)
    start_date: date
    end_date: date
    reason: str = Field(min_length=3, max_length=500)
    is_half_day: bool = False
    half_day_session: str | None = None


@router.post("/leaves", status_code=201)
async def create_leave(data: LeaveRequestIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await leave_service.request_leave(
        db, user, data.leave_type, data.start_date, data.end_date, data.reason,
        data.is_half_day, data.half_day_session
    )


@router.get("/leaves")
async def my_leaves(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await leave_service.list_leaves(db, user_id=user.id)


# ---------- Shift Management ----------
@router.get("/shifts")
async def list_shifts(_: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    shifts = await shift_service.list_shifts(db)
    return [
        {
            "id": s.id, "name": s.name, "code": s.code,
            "start_time": s.start_time.strftime("%H:%M"),
            "end_time": s.end_time.strftime("%H:%M"),
            "is_night_shift": s.is_night_shift,
            "is_active": s.is_active,
        }
        for s in shifts
    ]


class CreateShiftIn(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    code: str = Field(min_length=2, max_length=20)
    start_time: str = Field(pattern=HHMM)
    end_time: str = Field(pattern=HHMM)
    is_night_shift: bool = False


@router.post("/shifts", status_code=201)
async def create_shift(
    data: CreateShiftIn,
    user: User = Depends(require_permission("attendance.manage")),
    db: AsyncSession = Depends(get_db)
):
    sh, sm = (int(x) for x in data.start_time.split(":"))
    eh, em = (int(x) for x in data.end_time.split(":"))
    s = await shift_service.create_shift(
        db, user, data.name, data.code, time(sh, sm), time(eh, em), data.is_night_shift
    )
    return {
        "id": s.id, "name": s.name, "code": s.code,
        "start_time": s.start_time.strftime("%H:%M"),
        "end_time": s.end_time.strftime("%H:%M"),
        "is_night_shift": s.is_night_shift,
    }


class AssignShiftIn(BaseModel):
    user_id: int
    shift_id: int


@router.post("/shifts/assign")
async def assign_shift(
    data: AssignShiftIn,
    user: User = Depends(require_permission("attendance.manage")),
    db: AsyncSession = Depends(get_db)
):
    u = await shift_service.assign_user_shift(db, user, data.user_id, data.shift_id)
    return {"user_id": u.id, "shift_id": u.shift_id}


# ---------- Team (attendance.manage) ----------
@router.get("/team")
async def team(day: date | None = None, _: User = Depends(require_permission("attendance.manage")),
               db: AsyncSession = Depends(get_db)):
    return await svc.team_day(db, day or svc.today_local())


@router.get("/team/{user_id}/week")
async def team_member_week(user_id: int, start: date | None = None,
                           _: User = Depends(require_permission("attendance.manage")),
                           db: AsyncSession = Depends(get_db)):
    return await svc.week(db, user_id, start or svc.today_local())


@router.get("/team/{user_id}/month")
async def team_member_month(
    user_id: int,
    year: int | None = None,
    month: int | None = None,
    _: User = Depends(require_permission("attendance.manage")),
    db: AsyncSession = Depends(get_db)
):
    today_ = svc.today_local()
    return await svc.month(db, user_id, year or today_.year, month or today_.month)


@router.get("/approvals")
async def pending_regularizations(status: str = "pending", _: User = Depends(require_permission("attendance.manage")),
                                  db: AsyncSession = Depends(get_db)):
    return await svc.list_regularizations(db, status=status)


class DecideIn(BaseModel):
    approve: bool


@router.post("/approvals/{reg_id}")
async def decide(reg_id: int, data: DecideIn, user: User = Depends(require_permission("attendance.manage")),
                 db: AsyncSession = Depends(get_db)):
    return await svc.decide(db, user, reg_id, data.approve)


@router.get("/leaves/approvals")
async def pending_leaves(
    status: str = "pending",
    _: User = Depends(require_permission("attendance.manage")),
    db: AsyncSession = Depends(get_db)
):
    return await leave_service.list_leaves(db, status=status)


class DecideLeaveIn(BaseModel):
    approve: bool
    rejection_reason: str | None = None


@router.post("/leaves/approvals/{leave_id}")
async def decide_leave(
    leave_id: int,
    data: DecideLeaveIn,
    user: User = Depends(require_permission("attendance.manage")),
    db: AsyncSession = Depends(get_db)
):
    return await leave_service.decide_leave(db, user, leave_id, data.approve, data.rejection_reason)


# ---------- Excel Export ----------
@router.get("/export")
async def export_attendance(
    start_date: date = Query(...),
    end_date: date = Query(...),
    user_id: int | None = Query(None),
    status: str | None = Query(None),
    _: User = Depends(require_permission("attendance.manage")),
    db: AsyncSession = Depends(get_db),
):
    stream = await svc.export_excel(db, start_date, end_date, user_id=user_id, status_filter=status)
    filename = f"KJS_Attendance_{start_date}_{end_date}.xlsx"
    encoded_filename = urllib.parse.quote(filename)
    headers = {
        "Content-Disposition": f"attachment; filename=\"{filename}\"; filename*=UTF-8''{encoded_filename}",
        "Cache-Control": "no-cache",
    }
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )
