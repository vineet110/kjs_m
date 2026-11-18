"""Routes for the browser extension: `Authorization: Bearer <device key>`, no login cookie.
What to send and what comes back: extension/API.md. Area `monitoring` (config/modules.ini).

Why no CSRF header check here: CSRF abuses a cookie the browser sends by itself. These routes don't use
the cookie at all; a request without the right key is refused.
"""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.ini import cfg
from app.core.database import get_db
from app.core.errors import AppError
from app.core.modules import require_visible, running
from app.core.rate_limit import RateLimiter
from app.core.security import rate_key
from app.models.extension import ExtensionDevice
from app.models.user import User
from app.services import extension_service as ext
from app.services import monitor_service as monitor

router = APIRouter()
CONNECT_LIMIT = RateLimiter(lambda: 20, 3600)  # wrong codes per network per hour (codes can't be guessed in time)


async def device(request: Request, db: AsyncSession = Depends(get_db)) -> tuple[ExtensionDevice, User]:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise AppError(401, "bad_device", "This extension is not connected. Connect it again from My activity.")
    d, user = await ext.device_for_key(db, auth[7:].strip())
    require_visible(user, "monitoring")  # 404 module_off when the area is off for this person
    return d, user

device.module = "monitoring"  # read by the route map test (every route belongs to an area)


async def area_running():
    if not running("monitoring"):
        raise AppError(404, "module_off", "This part of the portal isn't available yet.", {"module": "monitoring"})

area_running.module = "monitoring"


class ConnectIn(BaseModel):
    code: str = Field(max_length=40)
    name: str = Field("", max_length=80)


@router.post("/connect", dependencies=[Depends(area_running)])
async def connect(data: ConnectIn, request: Request, db: AsyncSession = Depends(get_db)):
    key = rate_key(request.client.host if request.client else None)
    CONNECT_LIMIT.check(key, "Too many tries. Please wait an hour or ask the admin.")
    try:
        return await ext.connect(db, data.code, data.name)
    except AppError:
        CONNECT_LIMIT.hit(key)  # only wrong codes count
        raise


@router.get("/status")
async def status(dev=Depends(device), db: AsyncSession = Depends(get_db)):
    _, user = dev
    st = await monitor.state(db, user)
    c = cfg().monitoring
    return {"user_name": user.name, "checked_in": st["checked_in"], "on_break": st["on_break"],
            "server_time": datetime.now().astimezone().isoformat(),
            "config": {"send_minutes": c.send_minutes, "idle_warn_minutes": c.idle_warn_minutes,
                       "never_record": c.never_record, "screenshot_minutes": c.screenshot_minutes,
                       "image_quality": c.image_quality, "max_screenshot_kb": c.max_screenshot_kb}}


class VisitIn(BaseModel):
    id: str = Field(min_length=1, max_length=40)  # the extension's own id for this visit (same id = same visit)
    url: str = Field(max_length=4000)
    title: str = Field("", max_length=1000)
    started_at: AwareDatetime
    ended_at: AwareDatetime


class SitesIn(BaseModel):
    visits: list[VisitIn] = Field(max_length=ext.MAX_VISITS)


@router.post("/sites")
async def sites(data: SitesIn, dev=Depends(device), db: AsyncSession = Depends(get_db)):
    d, user = dev
    return await ext.save_visits(db, d, user, [v.model_dump() for v in data.visits])


class IdleIn(BaseModel):
    state: Literal["started", "ended"]
    at: AwareDatetime  # when it really started (the extension knows: now minus the idle time) or ended


@router.post("/idle")
async def idle(data: IdleIn, dev=Depends(device), db: AsyncSession = Depends(get_db)):
    _, user = dev
    if data.state == "started":
        await monitor.idle_started(db, user, data.at)
    else:
        await monitor.idle_ended(db, user, data.at)
    return {"ok": True}


@router.post("/screenshot")
async def screenshot(file: UploadFile = File(...), dev=Depends(device), db: AsyncSession = Depends(get_db)):
    _, user = dev
    data = await file.read(cfg().monitoring.max_screenshot_kb * 1024 + 1)
    shot = await monitor.save_screenshot(db, user, data, source="extension")
    return {"id": shot.id, "taken_at": shot.taken_at}


class ShareIn(BaseModel):
    state: Literal["started", "stopped", "refused"]


@router.post("/share")
async def share(data: ShareIn, dev=Depends(device), db: AsyncSession = Depends(get_db)):
    _, user = dev
    await monitor.share_event(db, user, data.state, source="extension")
    return {"ok": True}
