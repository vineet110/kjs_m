"""Home page hero: slides and stats. Admin routes need `content.edit` (Admin > Website > Hero); the public
route is what the home page reads (no login). Pictures are uploaded with the normal files route
(POST /files, owner_type "website", owner_id "hero", is_public true)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.errors import AppError
from app.models.user import User
from app.schemas.common import OneLine, SafeLink
from app.services import hero_service

router = APIRouter()
public_router = APIRouter()
editor = require_permission("content.edit")


@public_router.get("")
async def public_hero(db: AsyncSession = Depends(get_db)):
    return await hero_service.public(db)


@router.get("")
async def hero_admin(_: User = Depends(editor), db: AsyncSession = Depends(get_db)):
    return await hero_service.for_admin(db)


class SlideIn(BaseModel):
    eyebrow: OneLine = Field(default="", max_length=60)
    title: OneLine = Field(min_length=3, max_length=80)
    text: OneLine = Field(default="", max_length=240)
    cta_text: OneLine = Field(default="", max_length=30)
    cta_link: SafeLink = Field(default="", max_length=255)
    tone: str = Field(default="gold", max_length=20)
    image_ids: list[int] = Field(default_factory=list, max_length=hero_service.MAX_IMAGES)
    is_active: bool = True
    sort_order: int = 0


class SlidePatchIn(BaseModel):
    """Only the fields sent change: switching a slide off can't undo another admin's text edit."""
    eyebrow: OneLine | None = Field(default=None, max_length=60)
    title: OneLine | None = Field(default=None, min_length=3, max_length=80)
    text: OneLine | None = Field(default=None, max_length=240)
    cta_text: OneLine | None = Field(default=None, max_length=30)
    cta_link: SafeLink | None = Field(default=None, max_length=255)
    tone: str | None = Field(default=None, max_length=20)
    image_ids: list[int] | None = Field(default=None, max_length=hero_service.MAX_IMAGES)
    is_active: bool | None = None
    sort_order: int | None = None


def _no_nulls(changes: dict) -> dict:
    for k, v in changes.items():  # a field can be changed or emptied (""), never set to nothing
        if v is None:
            raise AppError(422, "bad_value", f"{k} can't be empty.")
    return changes


@router.post("/slides", status_code=201)
async def add_slide(data: SlideIn, user: User = Depends(editor), db: AsyncSession = Depends(get_db)):
    return await hero_service.save_slide(db, user, None, data.model_dump())


@router.patch("/slides/{slide_id}")
async def edit_slide(slide_id: int, data: SlidePatchIn, user: User = Depends(editor), db: AsyncSession = Depends(get_db)):
    return await hero_service.save_slide(db, user, slide_id, _no_nulls(data.model_dump(exclude_unset=True)))


@router.delete("/slides/{slide_id}", status_code=204)
async def remove_slide(slide_id: int, user: User = Depends(editor), db: AsyncSession = Depends(get_db)):
    await hero_service.delete_slide(db, user, slide_id)


class StatIn(BaseModel):
    number: OneLine = Field(min_length=1, max_length=12)
    label: OneLine = Field(min_length=2, max_length=60)
    is_active: bool = True
    sort_order: int = 0


class StatPatchIn(BaseModel):
    number: OneLine | None = Field(default=None, min_length=1, max_length=12)
    label: OneLine | None = Field(default=None, min_length=2, max_length=60)
    is_active: bool | None = None
    sort_order: int | None = None


@router.post("/stats", status_code=201)
async def add_stat(data: StatIn, user: User = Depends(editor), db: AsyncSession = Depends(get_db)):
    return await hero_service.save_stat(db, user, None, data.model_dump())


@router.patch("/stats/{stat_id}")
async def edit_stat(stat_id: int, data: StatPatchIn, user: User = Depends(editor), db: AsyncSession = Depends(get_db)):
    return await hero_service.save_stat(db, user, stat_id, _no_nulls(data.model_dump(exclude_unset=True)))


@router.delete("/stats/{stat_id}", status_code=204)
async def remove_stat(stat_id: int, user: User = Depends(editor), db: AsyncSession = Depends(get_db)):
    await hero_service.delete_stat(db, user, stat_id)
