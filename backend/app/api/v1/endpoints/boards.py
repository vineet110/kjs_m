"""Order boards. Create / finish: `boards.manage`. View and update a step: its members
(or `boards.manage`). Files: /files with owner_type=board, owner_id=<code>."""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import current_user, require_permission
from app.models.user import User
from app.services import board_service
from app.services.calendar_service import holiday_set

router = APIRouter()


class StepIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    percent: int | None = Field(default=None, ge=1, le=100)
    days: int | None = Field(default=None, ge=1, le=365)
    member_ids: list[int] = Field(default_factory=list)
    task_templates: list[str] = Field(default_factory=list, max_length=30)
    checklist: list[str] = Field(default_factory=list, max_length=30)


class BoardIn(BaseModel):
    code: str = Field(min_length=4, max_length=30)
    name: str = Field(min_length=2, max_length=255)
    client: str = Field(min_length=2, max_length=255)
    priority: Literal["low", "medium", "high"] = "medium"
    start: date
    deadline: date
    split_mode: Literal["percent", "days"] = "percent"
    notes: str = Field(default="", max_length=4000)
    steps: list[StepIn] = Field(min_length=1, max_length=20)


@router.get("")
async def boards(include_finished: bool = False, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Managers see all boards; everyone else sees the boards they are a member of."""
    return await board_service.list_boards(db, user, include_finished)


@router.post("", status_code=201)
async def create_board(data: BoardIn, user: User = Depends(require_permission("boards.manage")),
                       db: AsyncSession = Depends(get_db)):
    return await board_service.create(db, user, data)


class PreviewIn(BaseModel):
    start: date
    deadline: date
    split_mode: Literal["percent", "days"] = "percent"
    sizes: list[int] = Field(min_length=1, max_length=20)


@router.post("/preview")
async def preview_plan(data: PreviewIn, _: User = Depends(require_permission("boards.manage")),
                       db: AsyncSession = Depends(get_db)):
    """Planned step dates before saving (the create form shows them live)."""
    holidays = await holiday_set(db, data.start.year, data.deadline.year + 1)
    plan, late = board_service.plan_steps(data.start, data.deadline, data.split_mode, data.sizes, holidays)
    return {"steps": [{"start": s, "end": e} for s, e in plan], "plan_late": late}


@router.get("/{code}")
async def board(code: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await board_service.detail(db, user, code)


@router.post("/{code}/steps/{step_id}/done")
async def step_done(code: str, step_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await board_service.complete_step(db, user, code, step_id)


class CheckIn(BaseModel):
    index: int
    done: bool


@router.post("/{code}/steps/{step_id}/checklist")
async def check(code: str, step_id: int, data: CheckIn, user: User = Depends(current_user),
                db: AsyncSession = Depends(get_db)):
    return await board_service.toggle_check(db, user, code, step_id, data.index, data.done)


class FinishIn(BaseModel):
    final_status: Literal["Delivered", "Returned", "Cancelled"]


@router.post("/{code}/finish")
async def finish(code: str, data: FinishIn, user: User = Depends(require_permission("boards.manage")),
                 db: AsyncSession = Depends(get_db)):
    return await board_service.finish(db, user, code, data.final_status)
