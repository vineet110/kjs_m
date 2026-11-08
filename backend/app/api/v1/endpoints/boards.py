"""Order boards. Create: `boards.manage`. View and update (checklists, files): everyone on the board.
Mark a step done: its people (head included), the owner or `boards.manage`. People, step people,
finish: the owner (who created it) or `boards.manage`. Rules in board_service.
Files: /files with owner_type=board, owner_id=<code>."""
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import current_user, require_permission
from app.models.user import User
from app.services import board_service
from app.services.calendar_service import holiday_set

router = APIRouter()
MAX_BOARD_DAYS = 730  # an order runs at most 2 years: far-away dates would make the day-by-day plan very slow


def _check_dates(start: date, deadline: date) -> None:
    if deadline < start:
        raise ValueError("The deadline must be on or after the start date.")
    if (deadline - start).days > MAX_BOARD_DAYS:
        raise ValueError("A board can run at most 2 years.")


class StepIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    percent: int | None = Field(default=None, ge=1, le=100)
    days: int | None = Field(default=None, ge=1, le=365)
    member_ids: list[int] = Field(default_factory=list, max_length=50)  # at least 1: checked in the service
    head_ids: list[int] = Field(default_factory=list, max_length=50)  # must be among member_ids
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

    @model_validator(mode="after")
    def sane_dates(self):
        _check_dates(self.start, self.deadline)
        return self


class PlanStepIn(BaseModel):
    """A step in the edited plan. id = an existing step; no id = a new step (needs people)."""
    id: int | None = None
    name: str = Field(min_length=2, max_length=120)
    size: int = Field(ge=1, le=365)  # % of the time, or working days (split_mode)
    member_ids: list[int] = Field(default_factory=list, max_length=50)  # new steps only
    head_ids: list[int] = Field(default_factory=list, max_length=50)  # new steps only
    task_templates: list[str] = Field(default_factory=list, max_length=30)  # new steps only
    checklist: list[str] = Field(default_factory=list, max_length=30)  # new steps only


class PlanIn(BaseModel):
    start: date
    deadline: date
    split_mode: Literal["percent", "days"] = "percent"
    steps: list[PlanStepIn] = Field(min_length=1, max_length=20)  # in the new order
    version: str | None = Field(default=None, max_length=40)  # plan_version the editor started from

    @model_validator(mode="after")
    def sane_dates(self):
        _check_dates(self.start, self.deadline)
        return self


class LockIn(BaseModel):
    locked: bool


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
    sizes: list[Annotated[int, Field(ge=1, le=365)]] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def sane_dates(self):
        _check_dates(self.start, self.deadline)
        return self


@router.post("/preview")
async def preview_plan(data: PreviewIn, _: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Planned step dates before saving (the create form and the plan editor show them live). Any
    logged-in staff: anyone on a board may edit its unlocked plan, and this only works out dates."""
    holidays = await holiday_set(db, data.start.year, data.deadline.year + 1)
    plan, late = board_service.plan_steps(data.start, data.deadline, data.split_mode, data.sizes, holidays)
    return {"steps": [{"start": s, "end": e} for s, e in plan], "plan_late": late}


@router.get("/{code}")
async def board(code: str, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await board_service.detail(db, user, code)


@router.put("/{code}/plan")
async def edit_plan(code: str, data: PlanIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Dates, split and steps, saved together. Anyone on the board while unlocked; owner or
    boards.manage when locked. Rules in board_service.edit_plan."""
    return await board_service.edit_plan(db, user, code, data)


@router.post("/{code}/plan-lock")
async def plan_lock(code: str, data: LockIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await board_service.set_plan_lock(db, user, code, data.locked)  # owner or boards.manage


@router.get("/{code}/history")
async def board_history(code: str, before_id: int | None = Query(None, ge=1), limit: int = Query(50, ge=1, le=200),
                        user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Who changed what on the board, newest first. Read only (the audit log can't be edited).
    Everyone on the board."""
    return await board_service.history(db, user, code, before_id, limit)


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
async def finish(code: str, data: FinishIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await board_service.finish(db, user, code, data.final_status)  # owner or boards.manage


class PersonIn(BaseModel):
    user_id: int


@router.post("/{code}/people")
async def add_person(code: str, data: PersonIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await board_service.add_person(db, user, code, data.user_id)  # owner or boards.manage


@router.delete("/{code}/people/{user_id}")
async def remove_person(code: str, user_id: int, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await board_service.remove_person(db, user, code, user_id)  # owner or boards.manage


class StepPeopleIn(BaseModel):
    member_ids: list[int] = Field(min_length=1, max_length=50)
    head_ids: list[int] = Field(default_factory=list, max_length=50)


@router.put("/{code}/steps/{step_id}/people")
async def step_people(code: str, step_id: int, data: StepPeopleIn, user: User = Depends(current_user),
                      db: AsyncSession = Depends(get_db)):
    return await board_service.set_assignees(db, user, code, step_id, data.member_ids, data.head_ids)
