"""Laptop monitoring pages (/api/v1/monitoring): live status, unlock approvals, alerts, day reports and the
live stream. Rules and who-sees-whom: services/monitoring_service.py."""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_db
from app.core.deps import current_user, require_permission, session_user
from app.core.errors import AppError
from app.core.modules import require_visible
from app.models.user import User
from app.services import monitoring_service as svc

router = APIRouter()  # mounted with area("monitoring")
stream_router = APIRouter()  # no area dependency: that would hold a DB session for the whole stream


class DecisionIn(BaseModel):
    decision: Literal["approved", "rejected"]
    comment: str | None = Field(default=None, max_length=1000)


def _any_monitoring(user: User) -> None:
    if not svc.perms(user) & {svc.VIEW, svc.APPROVE}:
        raise AppError(403, "forbidden", "You don't have permission to do this.", {"needs": svc.VIEW})


@router.get("/live")
async def live(user: User = Depends(require_permission(svc.VIEW)), db: AsyncSession = Depends(get_db)):
    return await svc.live(db, user)


@router.get("/alerts")
async def alerts(open_only: bool = True, user: User = Depends(require_permission(svc.VIEW)),
                 db: AsyncSession = Depends(get_db)):
    return await svc.alerts(db, user, open_only)


@router.get("/unlock-requests")
async def unlock_requests(status: Literal["pending", "approved", "rejected", "all"] = "pending",
                          user: User = Depends(require_permission(svc.APPROVE)), db: AsyncSession = Depends(get_db)):
    return await svc.unlock_requests(db, user, status)


@router.post("/unlock-requests/{request_id}/decision")
async def decide(request_id: int, data: DecisionIn, user: User = Depends(require_permission(svc.APPROVE)),
                 db: AsyncSession = Depends(get_db)):
    return await svc.decide(db, user, request_id, data.decision, data.comment)


@router.get("/reports/daily")
async def daily(employee_id: str = Query(max_length=20), day: date = Query(alias="date"),
                user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await svc.daily(db, user, employee_id, day)


@router.get("/me/today")
async def my_day(day: date | None = Query(default=None, alias="date"), user: User = Depends(current_user),
                 db: AsyncSession = Depends(get_db)):
    from app.services.attendance_service import today_local
    return await svc.daily(db, user, str(user.id), day or today_local())


async def _stream_user(request: Request) -> int:
    """The login check for the stream, with its OWN short database session: a stream stays open for many
    minutes, and get_db would hold a database connection for all of it."""
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not token:
        raise AppError(401, "not_logged_in", "Please log in.")
    async with AsyncSessionLocal() as db:
        user = await session_user(db, token)
        if user is None:
            raise AppError(401, "not_logged_in", "Your session has ended. Please log in again.")
        require_visible(user, "monitoring")  # inside the session: the login check may have saved the row
        _any_monitoring(user)
        user_id = user.id
    return user_id


_stream_user.module = "monitoring"  # the route map test: it checks the area itself


@stream_router.get("/stream")
async def live_stream(request: Request, _: int = Depends(_stream_user)):
    """Server-Sent Events: `changed` the moment the monitoring server pushes something (no data in it: the
    page reloads what this person may see). nginx passes it unbuffered (deploy/nginx/default.conf)."""
    return StreamingResponse(svc.stream(request), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

