"""The feed the laptop-monitoring server polls (server to server, `X-Api-Key`).

Mounted at /api/v1/integrations/monitoring. The paths below are the ones the monitoring server's client
asks for (monitering/backend/app/services/crm_client.py CrmApiClient), so its CRM_BASE_URL is
http://backend:8000/api/v1/integrations/monitoring. Rules and timing: services/monitoring_link_service.py.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.service_key import require_monitoring_key
from app.services import monitoring_link_service as svc

router = APIRouter(dependencies=[Depends(require_monitoring_key())])


@router.get("/api/employees")
async def employees(db: AsyncSession = Depends(get_db)):
    return await svc.employees(db)


@router.get("/api/attendance/changes")
async def attendance_changes(since: datetime, db: AsyncSession = Depends(get_db)):
    return await svc.changes(db, since)


@router.get("/api/attendance/events")
async def attendance_events(employee_id: str = Query(max_length=20), from_: datetime = Query(alias="from"),
                            to: datetime = Query(), db: AsyncSession = Depends(get_db)):
    return await svc.events_for(db, employee_id, from_, to)
