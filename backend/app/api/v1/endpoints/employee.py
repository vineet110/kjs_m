"""Portal routes for any logged-in staff member. Each route names the permission it needs."""
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.user import User
from app.schemas.lead import LeadOut
from app.services import lead_service

router = APIRouter()


class LeadStatusIn(BaseModel):
    status: Literal["new", "contacted", "closed"]


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
    await lead_service.set_status(db, user, lead_id, data.status)
