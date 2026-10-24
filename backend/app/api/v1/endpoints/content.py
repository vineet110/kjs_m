"""Website content admin: texts + SEO, offers ticker, Koko facts and transcripts (`content.edit`),
partner applications (`leads.view_all`)."""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.models.user import User
from app.services import content_service

router = APIRouter()
editor = require_permission("content.edit")


@router.get("/texts")
async def texts(_: User = Depends(editor), db: AsyncSession = Depends(get_db)):
    return await content_service.all_texts_for_admin(db)


class TextIn(BaseModel):
    value: str | None = Field(default=None, max_length=20000)  # None = back to default


@router.put("/texts/{key}", status_code=204)
async def set_text(key: str, data: TextIn, user: User = Depends(editor), db: AsyncSession = Depends(get_db)):
    await content_service.set_text(db, user, key, data.value)


class OfferIn(BaseModel):
    text: str = Field(min_length=3, max_length=200)
    link: str = Field(default="", max_length=255)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = True
    sort_order: int = 0


@router.get("/offers")
async def offers(_: User = Depends(editor), db: AsyncSession = Depends(get_db)):
    return await content_service.list_offers(db)


@router.post("/offers", status_code=201)
async def add_offer(data: OfferIn, user: User = Depends(editor), db: AsyncSession = Depends(get_db)):
    return await content_service.save_offer(db, user, None, data.model_dump())


@router.patch("/offers/{offer_id}")
async def edit_offer(offer_id: int, data: OfferIn, user: User = Depends(editor), db: AsyncSession = Depends(get_db)):
    return await content_service.save_offer(db, user, offer_id, data.model_dump())


@router.delete("/offers/{offer_id}", status_code=204)
async def remove_offer(offer_id: int, user: User = Depends(editor), db: AsyncSession = Depends(get_db)):
    await content_service.delete_offer(db, user, offer_id)


@router.get("/koko-chats")
async def koko_chats(_: User = Depends(editor), db: AsyncSession = Depends(get_db)):
    return await content_service.list_chats(db)


@router.get("/partners")
async def partners(_: User = Depends(require_permission("leads.view_all")), db: AsyncSession = Depends(get_db)):
    return await content_service.list_partners(db)


class PartnerStatusIn(BaseModel):
    status: Literal["new", "approved", "rejected"]


@router.post("/partners/{partner_id}/status", status_code=204)
async def partner_status(partner_id: int, data: PartnerStatusIn,
                         user: User = Depends(require_permission("leads.view_all")), db: AsyncSession = Depends(get_db)):
    await content_service.set_partner_status(db, user, partner_id, data.status)
