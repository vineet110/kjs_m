"""Working-day maths. Pure functions first (easy to test), DB helpers at the bottom."""
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.calendar import Holiday
from app.models.user import User
from app.services import audit_service

SUNDAY = 6  # date.weekday(): Mon=0 … Sun=6


class CalendarService:
    @staticmethod
    def is_working_day(target_date: date, holidays: set[date] | list[date]) -> bool:
        return target_date.weekday() != SUNDAY and target_date not in holidays

    @staticmethod
    def add_working_days(start_date: date, num_days: int, holidays: set[date] | list[date]) -> date:
        """The date `num_days` working days after `start_date` (start day itself not counted)."""
        if num_days < 0:
            raise ValueError("num_days must be >= 0")
        current, added = start_date, 0
        while added < num_days:
            current += timedelta(days=1)
            if CalendarService.is_working_day(current, holidays):
                added += 1
        return current

    @staticmethod
    def working_days_between(start: date, end: date, holidays: set[date] | list[date]) -> int:
        """Working days in [start, end], both ends included. 0 if end < start."""
        days, current = 0, start
        while current <= end:
            if CalendarService.is_working_day(current, holidays):
                days += 1
            current += timedelta(days=1)
        return days


async def holiday_set(db: AsyncSession, year_from: int, year_to: int) -> set[date]:
    rows = await db.scalars(
        select(Holiday.day).where(Holiday.day >= date(year_from, 1, 1), Holiday.day <= date(year_to, 12, 31))
    )
    return set(rows.all())


async def list_holidays(db: AsyncSession, year: int) -> list[Holiday]:
    rows = await db.scalars(
        select(Holiday).where(Holiday.day >= date(year, 1, 1), Holiday.day <= date(year, 12, 31)).order_by(Holiday.day)
    )
    return list(rows.all())


async def add_holiday(db: AsyncSession, actor: User, day: date, name: str) -> Holiday:
    if await db.scalar(select(Holiday).where(Holiday.day == day)):
        raise AppError(409, "duplicate", "That date is already a holiday.")
    h = Holiday(day=day, name=name.strip())
    db.add(h)
    await db.flush()
    audit_service.record(db, actor=actor, action="holiday.added", entity_type="holiday",
                         entity_id=h.id, after={"day": day.isoformat(), "name": h.name})
    await db.commit()
    return h


async def remove_holiday(db: AsyncSession, actor: User, holiday_id: int) -> None:
    h = await db.get(Holiday, holiday_id)
    if h is None:
        raise AppError(404, "not_found", "Holiday not found.")
    audit_service.record(db, actor=actor, action="holiday.removed", entity_type="holiday",
                         entity_id=h.id, before={"day": h.day.isoformat(), "name": h.name})
    await db.delete(h)
    await db.commit()
