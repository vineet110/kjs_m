"""Auto-assign. Settings, import, preview, run now: `assign.manage`. Own batches: any staff."""
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import current_user, require_permission
from app.core.errors import AppError
from app.models.user import User
from app.services import assign_service

router = APIRouter()
MAX_IMPORT_BYTES = 10 * 1024 * 1024


@router.get("/overview")
async def overview(_: User = Depends(require_permission("assign.manage")), db: AsyncSession = Depends(get_db)):
    return await assign_service.overview(db)


@router.post("/import", status_code=201)
async def import_records(file: UploadFile = File(...), default_category: str = Form(""),
                         user: User = Depends(require_permission("assign.manage")), db: AsyncSession = Depends(get_db)):
    data = await file.read(MAX_IMPORT_BYTES + 1)
    if len(data) > MAX_IMPORT_BYTES:
        raise AppError(413, "too_big", "Max 10 MB per import.")
    return await assign_service.import_records(db, user, file.filename or "import", data, default_category)


@router.get("/preview")
async def preview(_: User = Depends(require_permission("assign.manage")), db: AsyncSession = Depends(get_db)):
    return await assign_service.preview(db)


@router.post("/run")
async def run_now(user: User = Depends(require_permission("assign.manage")), db: AsyncSession = Depends(get_db)):
    return await assign_service.run(db, user)


class CategoriesIn(BaseModel):
    categories: list[str] = Field(max_length=20)


@router.post("/staff/{user_id}/categories", status_code=204)
async def set_categories(user_id: int, data: CategoriesIn, user: User = Depends(require_permission("assign.manage")),
                         db: AsyncSession = Depends(get_db)):
    await assign_service.set_categories(db, user, user_id, data.categories)


# ---------- My batches ----------
@router.get("/my-batches")
async def my_batches(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await assign_service.my_batches(db, user)


class RecordIn(BaseModel):
    status: Literal["assigned", "done", "skipped"]
    outcome: str = Field(default="", max_length=300)


@router.patch("/records/{record_id}")
async def update_record(record_id: int, data: RecordIn, user: User = Depends(current_user),
                        db: AsyncSession = Depends(get_db)):
    return await assign_service.update_record(db, user, record_id, data.status, data.outcome)
