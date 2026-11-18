"""Website insights.

- public_router: the website's tracker sends what visitors do (no login). Always answers 204, even when
  nothing is saved (staff, robots, area off), so the website never shows an error for it.
- router: Reports > Website insights (permission insights.view, area site_insights).
"""
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.config.ini import cfg
from app.core.database import get_db
from app.core.deps import require_permission, visitor_keys
from app.core.errors import AppError
from app.models.user import User
from app.services import site_insights_service

public_router = APIRouter()
router = APIRouter()

# Size caps are security limits, so they stay in code (prompt.md 3.11.iv). How many events one send may
# carry is tunable (site_insights.ini max_events_per_send); this is only the hard ceiling.
MAX_EVENTS_HARD = 100


class EventIn(BaseModel):
    kind: Literal["page", "search", "click"]
    # The website page, a path like /en/products/x (never a full link to another site)
    path: str = Field(max_length=300, pattern=r"^/([^/\s]\S*)?$")
    referrer: str | None = Field(default=None, max_length=500)  # page: the site the visitor came from
    query: str | None = Field(default=None, max_length=200)  # search: the words typed
    results: int | None = Field(default=None, ge=0, le=100000)  # search: products found
    button: str | None = Field(default=None, max_length=40)  # click: data-track name


class EventsIn(BaseModel):
    visit_id: str = Field(pattern=r"^[A-Za-z0-9-]{8,40}$")  # random per browser tab, made by the website
    events: list[EventIn] = Field(min_length=1, max_length=MAX_EVENTS_HARD)

    @field_validator("events")
    @classmethod
    def not_too_many(cls, v: list[EventIn]) -> list[EventIn]:
        if len(v) > cfg().site_insights.max_events_per_send:
            raise ValueError(f"At most {cfg().site_insights.max_events_per_send} events at a time.")
        return v


@public_router.post("/events", status_code=204)
async def record_events(data: EventsIn, request: Request, db: AsyncSession = Depends(get_db)):
    await site_insights_service.record(
        db, data.visit_id, [e.model_dump() for e in data.events],
        user_agent=request.headers.get("user-agent", ""),
        # Logged in to the portal = staff: not counted. Faking the cookie only hides your own visits.
        is_staff=bool(request.cookies.get(settings.SESSION_COOKIE_NAME)),
        rate_key=visitor_keys(request)[1],
    )
    return Response(status_code=204)


@router.get("")
async def site_insights(days: int | None = Query(default=None, ge=1),
                        _: User = Depends(require_permission("insights.view")),
                        db: AsyncSession = Depends(get_db)):
    s = cfg().site_insights
    days = days or s.default_days
    if days > s.keep_days:
        raise AppError(422, "bad_range", f"Pick {s.keep_days} days or fewer: older visits are deleted.")
    return await site_insights_service.report(db, days)
