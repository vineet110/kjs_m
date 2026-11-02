"""Admin console routes. Every number here comes from the database (backlog D6: no fake stats)."""
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.ini import cfg, effective_with_sources, reload_now
from app.core.database import get_db
from app.core.deps import current_user, require_permission
from app.core.permissions import PERMISSIONS, effective_permissions
from app.models.audit import AuditLog
from app.models.catalog import Category, Product
from app.models.user import User
from app.schemas.auth import ApproveIn, UserOut
from app.schemas.catalog import ProductIn, ProductOut
from app.schemas.lead import LeadOut
from app.services import (analytics_service, attendance_service, audit_service, auth_service, calendar_service,
                          catalog_service, file_service, lead_service)

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


@router.get("/products", response_model=list[ProductOut])
async def all_products(_: User = Depends(require_permission("catalog.edit")), db: AsyncSession = Depends(get_db)):
    return await catalog_service.list_products(db, include_hidden=True)


class ProductUpdateIn(ProductIn):
    is_active: bool = True  # false = hidden from the website


@router.patch("/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: int, data: ProductUpdateIn,
    user: User = Depends(require_permission("catalog.edit")),
    db: AsyncSession = Depends(get_db),
):
    return await catalog_service.update_product(db, user, product_id, ProductIn(**data.model_dump(exclude={"is_active"}, exclude_unset=True)), data.is_active)


@router.get("/leads", response_model=list[LeadOut])
async def all_leads(
    status: str | None = None, owner: int | None = None, sla: str | None = None,
    offset: int = Query(0, ge=0),  # 500 per page: offset=500 for the next page
    user: User = Depends(require_permission("leads.view_all")),
    db: AsyncSession = Depends(get_db),
):
    return await lead_service.list_for(db, user, status, owner, sla, all_leads=True, limit=500, offset=offset)


class AssignIn(BaseModel):
    user_id: int


@router.post("/leads/{lead_id}/assign", status_code=204)
async def assign_lead(lead_id: int, data: AssignIn, user: User = Depends(require_permission("leads.view_all")),
                      db: AsyncSession = Depends(get_db)):
    await lead_service.assign(db, user, lead_id, data.user_id)


@router.get("/sla")
async def sla_settings(_: User = Depends(require_permission("leads.view_all"))):
    """Current SLA targets (edit config/sla.ini; applies within seconds)."""
    return cfg().sla.model_dump() | {"work_hours": f"{cfg().app.shift_start}-{cfg().app.shift_end}"}


@router.get("/approvals")
async def approvals(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """One inbox: each section only if you may approve it (null = not yours)."""
    perms = effective_permissions(user.role, user.permissions)
    signups = await auth_service.list_users(db, "pending") if "staff.approve" in perms else None
    return {
        "signups": [UserOut.model_validate(u).model_dump() for u in signups] if signups is not None else None,
        "regularizations": await attendance_service.list_regularizations(db, status="pending")
        if "attendance.manage" in perms else None,
        "file_deletes": await file_service.delete_requests(db) if "files.approve" in perms else None,
    }


@router.get("/analytics")
async def analytics(_: User = Depends(require_permission("staff.approve")), db: AsyncSession = Depends(get_db)):
    return await analytics_service.summary(db)


@router.get("/alerts")
async def alerts(_: User = Depends(require_permission("staff.approve")), db: AsyncSession = Depends(get_db)):
    c = cfg()
    return {"rules": {"board_thresholds": c.alerts.thresholds, "channels": c.alerts.channels,
                      "sla": c.sla.model_dump()},
            "log": await analytics_service.alert_log(db)}


@router.get("/config")
async def config_view(_: User = Depends(require_permission("staff.approve"))):
    """Effective tunable settings and their source. Secrets are never listed (they are in .env only)."""
    return effective_with_sources()


@router.post("/config/reload")
async def config_reload(user: User = Depends(require_permission("staff.approve")),
                        db: AsyncSession = Depends(get_db)):
    reload_now()
    audit_service.record(db, actor=user, action="config.reloaded", entity_type="config")
    await db.commit()
    return effective_with_sources()


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
    limit: int = Query(100, ge=1, le=500),
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
