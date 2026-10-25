"""Tasks. Own tasks: any logged-in staff member. Other people's: `tasks.assign`."""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import current_user
from app.models.user import User
from app.services import task_service

router = APIRouter()


class TaskIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    notes: str = Field(default="", max_length=4000)
    due_at: datetime | None = None
    assignee_id: int | None = None  # empty = me


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    notes: str | None = Field(default=None, max_length=4000)
    due_at: datetime | None = None
    status: Literal["todo", "doing", "done"] | None = None
    outcome: str | None = Field(default=None, max_length=200)


@router.get("")
async def list_tasks(status: str | None = None, source: str | None = None, due: str | None = None,
                     assignee_id: int | None = None, user: User = Depends(current_user),
                     db: AsyncSession = Depends(get_db)):
    """assignee_id: empty = mine, 0 = everyone's (tasks.assign), N = that person's (tasks.assign)."""
    return await task_service.list_tasks(db, user, status=status, source=source, due=due, assignee_id=assignee_id)


@router.get("/stats")
async def my_stats(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await task_service.stats(db, user.id)


@router.post("", status_code=201)
async def create_task(data: TaskIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await task_service.create(db, user, data.title, data.notes, data.due_at, data.assignee_id)


@router.patch("/{task_id}")
async def update_task(task_id: int, data: TaskPatch, user: User = Depends(current_user),
                      db: AsyncSession = Depends(get_db)):
    return await task_service.update(db, user, task_id, data.model_dump(exclude_unset=True))
