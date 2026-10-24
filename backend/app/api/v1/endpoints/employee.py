"""Portal routes for any logged-in staff member. Each route names the permission it needs."""
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import current_user, require_permission
from app.models.user import User
from app.schemas.lead import LeadOut
from app.services import lead_service, notification_service

router = APIRouter()


class LeadStatusIn(BaseModel):
    status: Literal["new", "contacted", "closed"]
    outcome: str = Field(default="", max_length=40)


class NoteIn(BaseModel):
    kind: Literal["note", "call", "email"] = "note"
    text: str = Field(min_length=1, max_length=2000)


class AssignIn(BaseModel):
    user_id: int


@router.get("/leads", response_model=list[LeadOut])
async def my_leads(
    status: str | None = None,
    user: User = Depends(require_permission("leads.view")),
    db: AsyncSession = Depends(get_db),
):
    return await lead_service.list_for(db, user, status)


@router.patch("/leads/{lead_id}", status_code=204)
async def update_lead(
    lead_id: int,
    data: LeadStatusIn,
    user: User = Depends(require_permission("leads.view")),
    db: AsyncSession = Depends(get_db),
):
    await lead_service.set_status(db, user, lead_id, data.status, data.outcome)


@router.get("/leads/{lead_id}/notes")
async def lead_notes(lead_id: int, user: User = Depends(require_permission("leads.view")),
                     db: AsyncSession = Depends(get_db)):
    return await lead_service.list_notes(db, user, lead_id)


@router.post("/leads/{lead_id}/notes", status_code=204)
async def add_lead_note(lead_id: int, data: NoteIn, user: User = Depends(require_permission("leads.view")),
                        db: AsyncSession = Depends(get_db)):
    await lead_service.add_note(db, user, lead_id, data.kind, data.text)


@router.post("/leads/{lead_id}/handover", status_code=204)
async def hand_over(lead_id: int, data: AssignIn, user: User = Depends(require_permission("leads.view")),
                    db: AsyncSession = Depends(get_db)):
    await lead_service.assign(db, user, lead_id, data.user_id)


@router.get("/colleagues")
async def colleagues(_: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Active staff, for 'hand over to…' pickers."""
    rows = await db.execute(select(User.id, User.name).where(User.status == "active").order_by(User.name))
    return [{"id": i, "name": n} for i, n in rows.all()]


# ---------- Notifications (the bell) ----------
@router.get("/notifications")
async def my_notifications(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await notification_service.list_mine(db, user)


class ReadIn(BaseModel):
    ids: list[int] = Field(default_factory=list)  # empty = mark all read


@router.post("/notifications/read", status_code=204)
async def read_notifications(data: ReadIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await notification_service.mark_read(db, user, data.ids)
