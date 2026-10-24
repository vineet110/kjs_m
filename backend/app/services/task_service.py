"""Tasks: one list per person, fed by every source (own, manager, lead, order board, batch).

Who may change a task: the assignee, whoever created it, or anyone with `tasks.assign`.
Giving a task to someone else needs `tasks.assign` and notifies them.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.permissions import effective_permissions
from app.models.task import Task
from app.models.user import User
from app.services import audit_service, notification_service
from app.services.attendance_service import local_day, to_utc

FIELDS = ("title", "notes", "due_at", "status", "outcome")


def _can_assign(user: User) -> bool:
    return "tasks.assign" in effective_permissions(user.role, user.permissions)


def _out(t: Task, names: dict[int, str], now: datetime) -> dict:
    overdue = t.status != "done" and t.due_at is not None and t.due_at < now
    return {"id": t.id, "title": t.title, "notes": t.notes, "due_at": t.due_at, "status": t.status,
            "outcome": t.outcome, "source": t.source, "source_ref": t.source_ref,
            "assignee_id": t.assignee_id, "assignee_name": names.get(t.assignee_id, ""),
            "created_by_name": names.get(t.created_by or 0, ""), "overdue": overdue,
            "completed_at": t.completed_at, "created_at": t.created_at}


async def _names(db: AsyncSession) -> dict[int, str]:
    return dict((await db.execute(select(User.id, User.name))).all())


def add(db: AsyncSession, *, assignee_id: int, title: str, source: str, created_by: int | None = None,
        due_at: datetime | None = None, notes: str = "", source_ref: str = "") -> Task:
    """Used by other services (order boards, batches) inside their own transaction."""
    t = Task(title=title[:200], notes=notes, due_at=due_at, status="todo", source=source,
             source_ref=source_ref, assignee_id=assignee_id, created_by=created_by)
    db.add(t)
    return t


async def create(db: AsyncSession, user: User, title: str, notes: str, due_at: datetime | None,
                 assignee_id: int | None) -> dict:
    assignee_id = assignee_id or user.id
    if assignee_id != user.id:
        if not _can_assign(user):
            raise AppError(403, "forbidden", "You can only add tasks for yourself.", {"needs": "tasks.assign"})
        target = await db.get(User, assignee_id)
        if target is None or target.status != "active":
            raise AppError(422, "bad_user", "Pick an active colleague.")
    t = add(db, assignee_id=assignee_id, title=title.strip(), notes=notes.strip(), due_at=due_at,
            source="own" if assignee_id == user.id else "manager", created_by=user.id)
    await db.flush()
    audit_service.record(db, actor=user, action="task.created", entity_type="task", entity_id=t.id,
                         after={"title": t.title, "assignee_id": assignee_id})
    if assignee_id != user.id:
        notification_service.notify(db, [assignee_id], "task.assigned", f"New task: {t.title}",
                                    f"From {user.name}.", "/employee/tasks")
    await db.commit()
    return _out(t, await _names(db), datetime.now(timezone.utc))


async def update(db: AsyncSession, user: User, task_id: int, changes: dict) -> dict:
    t = await db.get(Task, task_id)
    if t is None or not (user.id in (t.assignee_id, t.created_by) or _can_assign(user)):
        raise AppError(404, "not_found", "Task not found.")
    before = {k: getattr(t, k) for k in FIELDS if k in changes}
    for k in FIELDS:
        if k in changes:
            setattr(t, k, changes[k])
    if "status" in changes:
        t.completed_at = datetime.now(timezone.utc) if t.status == "done" else None
    audit_service.record(db, actor=user, action="task.updated", entity_type="task", entity_id=t.id,
                         before={k: str(v) for k, v in before.items()},
                         after={k: str(changes[k]) for k in before})
    await db.commit()
    return _out(t, await _names(db), datetime.now(timezone.utc))


async def list_tasks(db: AsyncSession, user: User, *, status: str | None = None, source: str | None = None,
                     due: str | None = None, assignee_id: int | None = None) -> list[dict]:
    now = datetime.now(timezone.utc)
    q = select(Task).order_by(Task.status == "done", Task.due_at.is_(None), Task.due_at, Task.id.desc())
    if assignee_id and assignee_id != user.id:
        if not _can_assign(user):
            raise AppError(403, "forbidden", "You can only see your own tasks.", {"needs": "tasks.assign"})
        q = q.where(Task.assignee_id == assignee_id)
    elif assignee_id == 0 and _can_assign(user):
        pass  # everyone's
    else:
        q = q.where(Task.assignee_id == user.id)
    if status:
        q = q.where(Task.status == status)
    if source:
        q = q.where(Task.source == source)
    if due == "overdue":
        q = q.where(Task.status != "done", Task.due_at < now)
    elif due == "today":
        end = to_utc(local_day(now) + timedelta(days=1), "00:00")  # midnight IST tonight
        q = q.where(Task.status != "done", Task.due_at < end)
    rows = (await db.scalars(q.limit(300))).all()
    names = await _names(db)
    return [_out(t, names, now) for t in rows]


async def stats(db: AsyncSession, user_id: int) -> dict:
    now = datetime.now(timezone.utc)
    rows = dict((await db.execute(select(Task.status, func.count()).where(Task.assignee_id == user_id)
                                  .group_by(Task.status))).all())
    overdue = await db.scalar(select(func.count()).select_from(Task).where(
        Task.assignee_id == user_id, Task.status != "done", Task.due_at < now))
    return {"total": sum(rows.values()), "done": rows.get("done", 0),
            "pending": rows.get("todo", 0) + rows.get("doing", 0), "overdue": overdue or 0}
