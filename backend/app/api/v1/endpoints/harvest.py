"""Client Schedulers / Lead Harvester endpoints.

Allows admins and sales managers to configure automated source schedulers (API, Open Data, RSS, Scrape),
trigger immediate runs, and inspect detailed ingestion audits with DPDP compliance metrics.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import current_user
from app.core.errors import AppError
from app.core.permissions import effective_permissions
from app.models.harvest import HarvestRun, HarvestSource
from app.models.user import User
from app.schemas.harvest import (
    HarvestRunOut,
    HarvestSourceIn,
    HarvestSourceOut,
    HarvestSourceUpdate,
)
from app.services import audit_service
from app.services.harvest_service import run_harvest_source

log = logging.getLogger("app.harvest.api")
router = APIRouter()


def require_harvest_access(user: User = Depends(current_user)) -> User:
    """Requires assign.manage, leads.view_all, or staff.approve."""
    perms = effective_permissions(user.role, user.permissions)
    allowed = {"assign.manage", "leads.view_all", "staff.approve"}
    if not allowed.intersection(perms):
        raise AppError(403, "forbidden", "You don't have permission to manage harvest schedulers.")
    return user


@router.get("/sources", response_model=list[HarvestSourceOut])
async def list_sources(
    _: User = Depends(require_harvest_access),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(HarvestSource).order_by(HarvestSource.id.asc())
    sources = (await db.scalars(stmt)).all()
    return sources


@router.post("/sources", response_model=HarvestSourceOut, status_code=201)
async def create_source(
    data: HarvestSourceIn,
    user: User = Depends(require_harvest_access),
    db: AsyncSession = Depends(get_db),
):
    source = HarvestSource(
        name=data.name,
        source_type=data.source_type,
        url=data.url,
        auth_env_var=data.auth_env_var,
        category=data.category,
        is_active=data.is_active,
        terms_checked=data.terms_checked,
        schedule_interval_minutes=data.schedule_interval_minutes,
        last_status="idle",
        created_by=user.id,
    )
    db.add(source)
    await db.flush()

    audit_service.record(
        db,
        actor=user,
        action="harvest_source.created",
        entity_type="harvest_source",
        entity_id=source.id,
        after={"name": source.name, "type": source.source_type, "url": source.url},
    )
    await db.commit()
    await db.refresh(source)
    return source


@router.put("/sources/{source_id}", response_model=HarvestSourceOut)
async def update_source(
    source_id: int,
    data: HarvestSourceUpdate,
    user: User = Depends(require_harvest_access),
    db: AsyncSession = Depends(get_db),
):
    source = await db.scalar(select(HarvestSource).where(HarvestSource.id == source_id))
    if not source:
        raise AppError(404, "source_not_found", "Harvest source not found.")

    before = {
        "name": source.name,
        "url": source.url,
        "category": source.category,
        "is_active": source.is_active,
        "terms_checked": source.terms_checked,
        "schedule_interval_minutes": source.schedule_interval_minutes,
    }

    if data.name is not None:
        source.name = data.name
    if data.url is not None:
        source.url = data.url
    if data.auth_env_var is not None:
        cleaned = data.auth_env_var.strip()
        if cleaned and not cleaned.replace("_", "").isalnum():
            raise AppError(400, "invalid_env_var", "auth_env_var must be alphanumeric/underscores.")
        source.auth_env_var = cleaned
    if data.category is not None:
        source.category = data.category
    if data.terms_checked is not None:
        source.terms_checked = data.terms_checked
    if data.is_active is not None:
        if source.source_type == "scrape" and data.is_active and not source.terms_checked:
            raise AppError(400, "terms_not_checked", "Cannot activate scrape source until terms are checked.")
        source.is_active = data.is_active
    if data.schedule_interval_minutes is not None:
        source.schedule_interval_minutes = data.schedule_interval_minutes

    audit_service.record(
        db,
        actor=user,
        action="harvest_source.updated",
        entity_type="harvest_source",
        entity_id=source.id,
        before=before,
        after={"name": source.name, "is_active": source.is_active},
    )
    await db.commit()
    await db.refresh(source)
    return source


@router.delete("/sources/{source_id}")
async def delete_source(
    source_id: int,
    user: User = Depends(require_harvest_access),
    db: AsyncSession = Depends(get_db),
):
    source = await db.scalar(select(HarvestSource).where(HarvestSource.id == source_id))
    if not source:
        raise AppError(404, "source_not_found", "Harvest source not found.")

    audit_service.record(
        db,
        actor=user,
        action="harvest_source.deleted",
        entity_type="harvest_source",
        entity_id=source.id,
        before={"name": source.name, "url": source.url},
    )
    await db.delete(source)
    await db.commit()
    return {"ok": True}


@router.post("/sources/{source_id}/run", response_model=HarvestRunOut)
async def trigger_run(
    source_id: int,
    _: User = Depends(require_harvest_access),
    db: AsyncSession = Depends(get_db),
):
    source = await db.scalar(select(HarvestSource).where(HarvestSource.id == source_id))
    if not source:
        raise AppError(404, "source_not_found", "Harvest source not found.")

    run = await run_harvest_source(db, source.id)
    return HarvestRunOut(
        id=run.id,
        source_id=source.id,
        source_name=source.name,
        source_type=source.source_type,
        status=run.status,
        found_count=run.found_count,
        accepted_count=run.accepted_count,
        dropped_count=run.dropped_count,
        drop_reasons=run.drop_reasons,
        error_message=run.error_message,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


@router.get("/runs", response_model=list[HarvestRunOut])
async def list_runs(
    source_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    _: User = Depends(require_harvest_access),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(HarvestRun, HarvestSource.name, HarvestSource.source_type)
        .join(HarvestSource, HarvestRun.source_id == HarvestSource.id)
        .order_by(desc(HarvestRun.id))
        .limit(limit)
    )
    if source_id:
        stmt = stmt.where(HarvestRun.source_id == source_id)

    rows = (await db.execute(stmt)).all()
    res = []
    for run, src_name, src_type in rows:
        res.append(
            HarvestRunOut(
                id=run.id,
                source_id=run.source_id,
                source_name=src_name,
                source_type=src_type,
                status=run.status,
                found_count=run.found_count,
                accepted_count=run.accepted_count,
                dropped_count=run.dropped_count,
                drop_reasons=run.drop_reasons,
                error_message=run.error_message,
                started_at=run.started_at,
                finished_at=run.finished_at,
            )
        )
    return res


@router.get("/stats")
async def harvest_stats(
    _: User = Depends(require_harvest_access),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    total_sources = await db.scalar(select(func.count()).select_from(HarvestSource)) or 0
    active_sources = (
        await db.scalar(select(func.count()).select_from(HarvestSource).where(HarvestSource.is_active == True))  # noqa: E712
        or 0
    )
    total_runs = await db.scalar(select(func.count()).select_from(HarvestRun)) or 0
    accepted = await db.scalar(select(func.sum(HarvestRun.accepted_count))) or 0
    dropped = await db.scalar(select(func.sum(HarvestRun.dropped_count))) or 0

    return {
        "total_sources": total_sources,
        "active_sources": active_sources,
        "total_runs": total_runs,
        "total_accepted": int(accepted),
        "total_dropped": int(dropped),
    }
