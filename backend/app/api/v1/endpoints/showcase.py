"""Website showcase: partner logos (sliding strip) and activity lines (pop-ups). Admin routes need `content.edit`
(Admin > Website); the public routes are what the website reads (no login). Logos are uploaded with the normal
files route (POST /files, owner_type "website", owner_id "partners", is_public true)."""
from fastapi import APIRouter, Depends
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.errors import AppError
from app.models.user import User
from app.schemas.common import OneLine
from app.services import showcase_service

router = APIRouter()
public_router = APIRouter()
editor = require_permission("content.edit")


def _no_nulls(changes: dict, may_be_null: tuple[str, ...] = ()) -> dict:
    for k, v in changes.items():  # a field can be changed, never set to nothing (except a logo: name only)
        if v is None and k not in may_be_null:
            raise AppError(422, "bad_value", f"{k} can't be empty.")
    return changes


# ---------- Public (no login) ----------
@public_router.get("/brand-partners")  # not /partners: that is the partner application form (POST)
async def public_partners(db: AsyncSession = Depends(get_db)):
    return await showcase_service.public_partners(db)


@public_router.get("/activity")
async def public_activity(db: AsyncSession = Depends(get_db)):
    return await showcase_service.public_lines(db)


# ---------- Partners ----------
class PartnerIn(BaseModel):
    name: OneLine = Field(min_length=2, max_length=60)
    logo_file_id: int | None = None
    is_active: bool = True
    sort_order: int = 0


class PartnerPatchIn(BaseModel):
    name: OneLine | None = Field(default=None, min_length=2, max_length=60)
    logo_file_id: int | None = None  # null = remove the logo (name only)
    is_active: bool | None = None
    sort_order: int | None = None


@router.get("/partners")
async def partners(_: User = Depends(editor), db: AsyncSession = Depends(get_db)):
    return await showcase_service.partners_for_admin(db)


@router.post("/partners", status_code=201)
async def add_partner(data: PartnerIn, user: User = Depends(editor), db: AsyncSession = Depends(get_db)):
    return await showcase_service.save_partner(db, user, None, data.model_dump())


@router.patch("/partners/{partner_id}")
async def edit_partner(partner_id: int, data: PartnerPatchIn, user: User = Depends(editor), db: AsyncSession = Depends(get_db)):
    changes = _no_nulls(data.model_dump(exclude_unset=True), may_be_null=("logo_file_id",))
    return await showcase_service.save_partner(db, user, partner_id, changes)


@router.delete("/partners/{partner_id}", status_code=204)
async def remove_partner(partner_id: int, user: User = Depends(editor), db: AsyncSession = Depends(get_db)):
    await showcase_service.delete_partner(db, user, partner_id)


# ---------- Activity lines ----------
class LineIn(BaseModel):
    text: OneLine = Field(min_length=5, max_length=120)
    happened_at: AwareDatetime  # with a time zone: the website shows "2 hours ago" from it
    is_active: bool = True
    sort_order: int = 0


class LinePatchIn(BaseModel):
    text: OneLine | None = Field(default=None, min_length=5, max_length=120)
    happened_at: AwareDatetime | None = None
    is_active: bool | None = None
    sort_order: int | None = None


@router.get("/activity")
async def activity(_: User = Depends(editor), db: AsyncSession = Depends(get_db)):
    return await showcase_service.lines_for_admin(db)


@router.post("/activity", status_code=201)
async def add_line(data: LineIn, user: User = Depends(editor), db: AsyncSession = Depends(get_db)):
    return await showcase_service.save_line(db, user, None, data.model_dump())


@router.patch("/activity/{line_id}")
async def edit_line(line_id: int, data: LinePatchIn, user: User = Depends(editor), db: AsyncSession = Depends(get_db)):
    return await showcase_service.save_line(db, user, line_id, _no_nulls(data.model_dump(exclude_unset=True)))


@router.delete("/activity/{line_id}", status_code=204)
async def remove_line(line_id: int, user: User = Depends(editor), db: AsyncSession = Depends(get_db)):
    await showcase_service.delete_line(db, user, line_id)
