"""Work pages, read-only. Area `monitoring` (config/modules.ini).

- /work/team, /work/{user_id}/...: Team work for people with `monitor.view` (admins have it).
- /work/me/...: My work. Any logged-in staff member, always their OWN data (no id is taken from the request).
"""
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import current_user, require_permission
from app.core.errors import AppError
from app.models.user import User
from app.services import attendance_service as att
from app.services import monitor_service as monitor
from app.services import work_service as svc

router = APIRouter()
MONITOR = require_permission("monitor.view")


def _range(start: date | None, end: date | None) -> tuple[date, date]:
    today = att.today_local()
    return start or end or today, end or start or today


def _kinds(kinds: str | None) -> set[str] | None:
    if not kinds:
        return None
    asked = {k.strip() for k in kinds.split(",") if k.strip()}
    unknown = asked - set(svc.KINDS)
    if unknown:
        raise AppError(400, "bad_kind", "Unknown timeline type.", {"unknown": sorted(unknown), "allowed": svc.KINDS})
    return asked


def _month(year: int | None, month: int | None) -> tuple[int, int]:
    today = att.today_local()
    return year or today.year, month or today.month


# ---------- My work (own data) ----------
@router.get("/me/overview")
async def my_overview(start: date | None = Query(None, alias="from"), end: date | None = Query(None, alias="to"),
                      user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await svc.overview(db, user, *_range(start, end))


@router.get("/me/timeline")
async def my_timeline(start: date | None = Query(None, alias="from"), end: date | None = Query(None, alias="to"),
                      kinds: str | None = None, before: datetime | None = None,
                      user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await svc.timeline(db, user.id, *_range(start, end), _kinds(kinds), before)


@router.get("/me/tasks")
async def my_tasks(start: date | None = Query(None, alias="from"), end: date | None = Query(None, alias="to"),
                   user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await svc.tasks(db, user.id, *_range(start, end))


@router.get("/me/attendance")
async def my_attendance(year: int | None = Query(None, ge=2000, le=2100), month: int | None = Query(None, ge=1, le=12),
                        user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await att.month(db, user.id, *_month(year, month))


# ---------- Team work (monitor.view) ----------
@router.get("/team")
async def team(day: date | None = None, _: User = Depends(MONITOR), db: AsyncSession = Depends(get_db)):
    return await svc.team_day(db, day or att.today_local())


@router.get("/{user_id}/overview")
async def person_overview(user_id: int, start: date | None = Query(None, alias="from"),
                          end: date | None = Query(None, alias="to"),
                          viewer: User = Depends(MONITOR), db: AsyncSession = Depends(get_db)):
    u = await svc.person(db, user_id)
    out = await svc.overview(db, u, *_range(start, end))
    await svc.note_view(db, viewer, u)
    return out


@router.get("/{user_id}/timeline")
async def person_timeline(user_id: int, start: date | None = Query(None, alias="from"),
                          end: date | None = Query(None, alias="to"), kinds: str | None = None,
                          before: datetime | None = None,
                          viewer: User = Depends(MONITOR), db: AsyncSession = Depends(get_db)):
    u = await svc.person(db, user_id)
    out = await svc.timeline(db, u.id, *_range(start, end), _kinds(kinds), before)
    await svc.note_view(db, viewer, u)
    return out


@router.get("/{user_id}/tasks")
async def person_tasks(user_id: int, start: date | None = Query(None, alias="from"),
                       end: date | None = Query(None, alias="to"),
                       _: User = Depends(MONITOR), db: AsyncSession = Depends(get_db)):
    u = await svc.person(db, user_id)
    return await svc.tasks(db, u.id, *_range(start, end))


@router.get("/{user_id}/attendance")
async def person_attendance(user_id: int, year: int | None = Query(None, ge=2000, le=2100),
                            month: int | None = Query(None, ge=1, le=12),
                            _: User = Depends(MONITOR), db: AsyncSession = Depends(get_db)):
    u = await svc.person(db, user_id)
    return await att.month(db, u.id, *_month(year, month))


@router.get("/{user_id}/screenshots")
async def person_screenshots(user_id: int, day: date | None = None,
                             _: User = Depends(MONITOR), db: AsyncSession = Depends(get_db)):
    u = await svc.person(db, user_id)
    d = day or att.today_local()
    return {"day": d, "screenshots": await monitor.screenshots_of(db, u.id, d),
            "gaps": await monitor.share_gaps(db, u.id, d)}


@router.get("/{user_id}/screenshots/{shot_id}/image")
async def person_screenshot_image(user_id: int, shot_id: int,
                                  _: User = Depends(MONITOR), db: AsyncSession = Depends(get_db)):
    data = await monitor.screenshot_image(db, user_id, shot_id)
    # private: the browser may keep it for this page only; never a shared cache
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=300"})
