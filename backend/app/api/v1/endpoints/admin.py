"""Admin console routes. Every number here comes from the database (backlog D6: no fake stats)."""
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_permission
from app.core.permissions import PERMISSIONS
from app.models.audit import AuditLog
from app.models.catalog import Category, Product
from app.models.user import User
from app.schemas.auth import ApproveIn, UserOut
from app.schemas.catalog import ProductIn, ProductOut
from app.services import auth_service, calendar_service, catalog_service, lead_service

router = APIRouter()


@router.get("/stats")
async def stats(_: User = Depends(require_permission("staff.approve")), db: AsyncSession = Depends(get_db)):
    users = dict((await db.execute(select(User.status, func.count()).group_by(User.status))).all())
    leads = await lead_service.counts(db)
    return {
        "leads_total": sum(leads.values()),
        "leads_new": leads.get("new", 0),
        "staff_pending": users.get("pending", 0),
        "staff_active": users.get("active", 0),
        "products": await db.scalar(select(func.count()).select_from(Product).where(Product.is_active)),
        "categories": await db.scalar(select(func.count()).select_from(Category).where(Category.is_active)),
    }


@router.get("/permissions")
async def permissions(_: User = Depends(require_permission("staff.approve"))):
    return [{"key": k, "label": v} for k, v in PERMISSIONS.items()]


@router.get("/users", response_model=list[UserOut])
async def users(
    status: str | None = None,
    _: User = Depends(require_permission("staff.approve")),
    db: AsyncSession = Depends(get_db),
):
    return await auth_service.list_users(db, status)


@router.post("/users/{user_id}/approve", response_model=UserOut)
async def approve_user(
    user_id: int, data: ApproveIn,
    admin: User = Depends(require_permission("staff.approve")),
    db: AsyncSession = Depends(get_db),
):
    return await auth_service.approve(db, admin, user_id, data.permissions)


class StatusIn(BaseModel):
    status: Literal["active", "disabled"]


@router.post("/users/{user_id}/status", response_model=UserOut)
async def set_user_status(
    user_id: int, data: StatusIn,
    admin: User = Depends(require_permission("staff.approve")),
    db: AsyncSession = Depends(get_db),
):
    return await auth_service.set_status(db, admin, user_id, data.status)


@router.post("/products", response_model=ProductOut, status_code=201)
async def create_product(
    data: ProductIn,
    user: User = Depends(require_permission("catalog.edit")),
    db: AsyncSession = Depends(get_db),
):
    return await catalog_service.create_product(db, user, data)


class AuditOut(BaseModel):
    id: int
    at: datetime
    actor_label: str
    action: str
    entity_type: str
    entity_id: str | None
    after: dict | None

    model_config = {"from_attributes": True}


@router.get("/audit", response_model=list[AuditOut])
async def audit(
    limit: int = 100,
    _: User = Depends(require_permission("audit.view")),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(min(limit, 500)))
    return list(rows.all())


class HolidayIn(BaseModel):
    day: date
    name: str


class HolidayOut(HolidayIn):
    id: int

    model_config = {"from_attributes": True}


@router.get("/holidays", response_model=list[HolidayOut])
async def holidays(year: int, _: User = Depends(require_permission("calendar.edit")), db: AsyncSession = Depends(get_db)):
    return await calendar_service.list_holidays(db, year)


@router.post("/holidays", response_model=HolidayOut, status_code=201)
async def add_holiday(data: HolidayIn, user: User = Depends(require_permission("calendar.edit")), db: AsyncSession = Depends(get_db)):
    return await calendar_service.add_holiday(db, user, data.day, data.name)


@router.delete("/holidays/{holiday_id}", status_code=204)
async def remove_holiday(holiday_id: int, user: User = Depends(require_permission("calendar.edit")), db: AsyncSession = Depends(get_db)):
    await calendar_service.remove_holiday(db, user, holiday_id)
