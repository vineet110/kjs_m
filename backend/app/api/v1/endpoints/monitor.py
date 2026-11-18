"""Monitoring for the logged-in person (the portal sends these). Area `monitoring` (config/modules.ini).

Always the person's OWN data: the id comes from the login, never from the request. Nothing is saved while
checked out (monitor_service checks it).
"""
from typing import Literal

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.ini import cfg
from app.core.database import get_db
from app.core.deps import current_user
from app.core.errors import AppError
from app.models.user import User
from app.services import monitor_service as svc

router = APIRouter()


@router.get("/state")
async def state(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await svc.state(db, user)


class DeviceIn(BaseModel):
    device: Literal["laptop", "phone"]


@router.post("/device")
async def device(data: DeviceIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await svc.set_device(db, user, data.device)
    return {"ok": True}


@router.post("/screenshot")
async def screenshot(file: UploadFile = File(...), user: User = Depends(current_user),
                     db: AsyncSession = Depends(get_db)):
    limit = cfg().monitoring.max_screenshot_kb * 1024
    data = await file.read(limit + 1)  # never read more than the limit (+1 to know it was too big)
    shot = await svc.save_screenshot(db, user, data)
    return {"id": shot.id, "taken_at": shot.taken_at}


class ShareIn(BaseModel):
    state: Literal["started", "stopped", "refused"]


@router.post("/share")
async def share(data: ShareIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await svc.share_event(db, user, data.state)
    return {"ok": True}


@router.post("/break/start")
async def break_start(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await svc.start_break(db, user)


@router.post("/break/end")
async def break_end(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await svc.end_break(db, user)


class ReasonIn(BaseModel):
    reason: Literal["call", "meeting", "other"]
    note: str = Field("", max_length=200)


@router.post("/idle/{idle_id}/reason")
async def idle_reason(idle_id: int, data: ReasonIn, user: User = Depends(current_user),
                      db: AsyncSession = Depends(get_db)):
    if data.reason == "other" and not data.note.strip():
        raise AppError(400, "note_needed", "Please say what you were doing.")
    await svc.set_idle_reason(db, user, idle_id, data.reason, data.note)
    return {"ok": True}
