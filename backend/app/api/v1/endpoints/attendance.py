"""Attendance and availability. Own data: any logged-in staff member.
Team views and approvals: the `attendance.manage` permission."""
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import current_user, require_permission
from app.models.user import User
from app.services import attendance_service as svc
from app.services import calendar_service

router = APIRouter()
HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"


@router.get("/today")
async def today(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await svc.today(db, user)


@router.post("/check-in")
async def check_in(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await svc.check_in(db, user)
    return await svc.today(db, user)


@router.post("/check-out")
async def check_out(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await svc.check_out(db, user)
    return await svc.today(db, user)


@router.get("/week")
async def my_week(start: date | None = None, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await svc.week(db, user.id, start or svc.today_local())


@router.get("/holidays")
async def holidays(year: int | None = None, _: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = await calendar_service.list_holidays(db, year or svc.today_local().year)
    return [{"id": h.id, "day": h.day, "name": h.name} for h in rows]


class AvailabilityIn(BaseModel):
    available: bool


@router.post("/availability")
async def availability(data: AvailabilityIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return {"is_available": await svc.set_availability(db, user, data.available)}


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
