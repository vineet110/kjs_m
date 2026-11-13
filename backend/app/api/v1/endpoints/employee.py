"""Portal routes for any logged-in staff member. Each route names the permission it needs."""
from typing import Literal

from fastapi import APIRouter, Depends, File, Query, UploadFile
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import current_user, require_permission
from app.core.rate_limit import lead_file_limiter
from app.models.user import User
from app.schemas.lead import Contact, InternalLeadIn, LeadOut
from app.services import lead_reader, lead_service, notification_service

router = APIRouter()


class LeadStatusIn(BaseModel):
    status: Literal["new", "contacted", "closed"]
    outcome: str = Field(default="", max_length=40)


class NoteIn(BaseModel):
    kind: Literal["note", "call", "email"] = "note"
    text: str = Field(min_length=1, max_length=2000)


class AssignIn(BaseModel):
    user_id: int


class LeadTaskIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    notes: str = Field(default="", max_length=4000)
    due_at: AwareDatetime | None = None  # with a time zone ("...Z")


@router.get("/leads", response_model=list[LeadOut])
async def my_leads(
    status: str | None = None,
    source: str | None = Query(None, max_length=30),  # e.g. "koko", "internal"
    user: User = Depends(require_permission("leads.view")),
    db: AsyncSession = Depends(get_db),
):
    return await lead_service.list_for(db, user, status, source=source)


@router.post("/leads", response_model=LeadOut, status_code=201)
async def add_internal_lead(data: InternalLeadIn, user: User = Depends(require_permission("leads.view")),
                            db: AsyncSession = Depends(get_db)):
    """Internal lead: typed in by staff (a call, a fair, a walk-in)."""
    return await lead_service.create_internal(db, user, data)


@router.post("/leads/read-file")
async def read_lead_file(file: UploadFile = File(...), user: User = Depends(require_permission("leads.view")),
                         db: AsyncSession = Depends(get_db)):
    """Read an Excel / CSV file to fill the New internal lead form. Nothing is saved."""
    lead_file_limiter.check(f"user:{user.id}", "Too many files read in an hour. Please try again later.")
    data = await file.read(lead_reader.MAX_BYTES + 1)
    return await lead_service.read_lead_file(db, file.filename or "", data)


@router.get("/leads/same-person")
async def same_person(phone: str = Query("", max_length=40), email: str = Query("", max_length=255),
                      user: User = Depends(require_permission("leads.view")), db: AsyncSession = Depends(get_db)):
    """Before saving a lead: how many leads this person already has (that I can see), and the newest one."""
    return await lead_service.same_person(db, user, phone, email)


@router.get("/contacts", response_model=list[Contact])
async def contacts(user: User = Depends(require_permission("leads.view")), db: AsyncSession = Depends(get_db)):
    """One row per person who sent enquiries. leads.view_all sees everyone, others their own + unassigned."""
    return await lead_service.contacts(db, user)


@router.get("/contacts/{lead_id}")
async def contact(lead_id: int, user: User = Depends(require_permission("leads.view")),
                  db: AsyncSession = Depends(get_db)):
    """One lead, plus the same person's other enquiries."""
    return await lead_service.contact_detail(db, user, lead_id)


@router.get("/leads/{lead_id}/tasks")
async def lead_tasks(lead_id: int, user: User = Depends(require_permission("leads.view")),
                     db: AsyncSession = Depends(get_db)):
    return await lead_service.lead_tasks(db, user, lead_id)


@router.post("/leads/{lead_id}/tasks", status_code=201)
async def add_lead_task(lead_id: int, data: LeadTaskIn, user: User = Depends(require_permission("leads.view")),
                        db: AsyncSession = Depends(get_db)):
    return await lead_service.add_lead_task(db, user, lead_id, data.title, data.notes, data.due_at)


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
