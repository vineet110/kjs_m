"""Job titles ("Sales Executive"): the list admins pick from on the user form, and add to from it.
A title is a label only: everyone is an employee, and permissions decide what they may do."""
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.job_title import JobTitle
from app.models.user import User
from app.services import audit_service


async def list_titles(db: AsyncSession) -> list[str]:
    return list((await db.scalars(select(JobTitle.name).order_by(func.lower(JobTitle.name)))).all())


async def find(db: AsyncSession, name: str) -> str | None:
    """The title as the list spells it, matched whatever its case; None if it isn't in the list."""
    return await db.scalar(select(JobTitle.name).where(func.lower(JobTitle.name) == name.strip().lower()))


async def add(db: AsyncSession, admin: User, name: str) -> str:
    """Adds a title (admin only). One that is already there (any case) is simply returned."""
    if admin.role != "admin":
        raise AppError(403, "forbidden", "Only an admin can add a job title.")
    name = " ".join(name.split())
    if existing := await find(db, name):
        return existing
    db.add(JobTitle(name=name, created_by=admin.id))
    try:
        await db.flush()
    except IntegrityError:  # the same title added at the same moment by another admin
        await db.rollback()
        return await find(db, name) or name
    audit_service.record(db, actor=admin, action="job_title.added", entity_type="job_title", after={"name": name})
    await db.commit()
    return name
