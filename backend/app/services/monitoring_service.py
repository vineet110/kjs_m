"""Laptop monitoring inside the CRM (INTEGRATION_PLAN.md Phase 3): live status, unlock approvals, alerts,
reports, and the bell, read from the monitoring server.

Who sees what (the CRM decides; the monitoring server checks unlock decisions again):
- admins: everyone;
- others with monitoring.view / monitoring.approve: only the people who report to them (users.reporting_to);
- everyone: their own day report.

No waiting, both ways:
- the monitoring server pushes alerts, laptop states and unlock requests the moment they change
  (POST /api/v1/integrations/monitoring/api/monitoring/push -> handle_push);
- handle_push rings the right bells and tells every open monitoring tab at once over its live stream
  (GET /api/v1/monitoring/stream, Server-Sent Events), and the page reloads what changed;
- safety nets: the `monitoring_alerts_catchup` job reads recent alerts every jobs tick (a push that failed
  still rings the bell) and the page reloads every page_refresh_seconds anyway.
The API key never reaches a browser: every call to the monitoring server is made from here.
"""
import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta, timezone

import httpx
from fastapi import Request
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.config.ini import cfg
from app.core.errors import AppError
from app.core.permissions import effective_permissions
from app.jobs.runner import job
from app.models.monitoring_link import MonitoringAlertSeen, MonitoringLinkState
from app.models.user import User
from app.services import audit_service, monitoring_link_service, notification_service

log = logging.getLogger(__name__)

VIEW, APPROVE = "monitoring.view", "monitoring.approve"
STREAM_MAX = timedelta(minutes=30)  # a live stream ends after this and the browser reconnects (re-checks the login)
PAGE = "/admin/monitoring"
# Alert types that ring a bell, and who hears them. The rest (agent.offline, crm.sync_failed) show on the page.
TO_MANAGER = {"lock.requested"}
TO_APPROVERS = {"lock.escalated", "agent.tampered"}
TITLES = {
    "lock.requested": "{name}'s laptop is locked: unlock request waiting",
    "lock.escalated": "Unlock request for {name} is still waiting",
    "agent.tampered": "Monitoring on {name}'s laptop looks switched off",
}


def perms(user: User) -> set[str]:
    return effective_permissions(user.role, user.permissions)


# ---------- Calling the monitoring server ----------
async def call(method: str, path: str, *, params: dict | None = None, body: dict | None = None,
               actor: User | None = None) -> dict:
    if not settings.MONITORING_BASE_URL or not settings.MONITORING_API_KEY:
        raise AppError(503, "monitoring_not_set_up", "Laptop monitoring is not connected on this server yet.")
    headers = {"X-Actor": str(actor.id)} if actor else {}
    try:
        r = await monitoring_link_service.http().request(
            method, path, params=params, json=body, headers=headers, timeout=cfg().monitoring_link.call_timeout_seconds)
    except httpx.HTTPError as e:
        log.warning("monitoring.unreachable", extra={"path": path, "error": type(e).__name__})
        raise AppError(503, "monitoring_unreachable", "The monitoring server is not answering. Try again in a minute.")
    if r.status_code >= 500 or r.status_code == 401:  # 401: our key is wrong (a setup problem, not the user's)
        log.warning("monitoring.error", extra={"path": path, "status": r.status_code})
        raise AppError(503, "monitoring_unreachable", "The monitoring server is not answering. Try again in a minute.")
    if r.status_code >= 400:
        try:
            detail = str(r.json().get("detail", ""))
        except ValueError:
            detail = ""
        code = {403: "monitoring_forbidden", 404: "monitoring_not_found", 409: "monitoring_conflict"}.get(
            r.status_code, "monitoring_refused")
        raise AppError(r.status_code if r.status_code in (403, 404, 409) else 422, code,
                       detail or "The monitoring server refused this.")
    return r.json()


# ---------- Who may see whom ----------
async def team(db: AsyncSession, user: User) -> set[str] | None:
    """CRM ids this person may see: None = everyone (admins), else the people who report to them."""
    if user.role == "admin":
        return None
    ids = (await db.scalars(select(User.id).where(User.reporting_to == user.id))).all()
    return {str(i) for i in ids}


def _mine(rows: list[dict], allowed: set[str] | None) -> list[dict]:
    return rows if allowed is None else [r for r in rows if r.get("employee_id") in allowed]


async def live(db: AsyncSession, user: User) -> dict:
    data = await call("GET", "/api/crm/live-status")
    return {"employees": _mine(data.get("employees", []), await team(db, user))}


async def alerts(db: AsyncSession, user: User, open_only: bool = True) -> dict:
    data = await call("GET", "/api/crm/alerts", params={"open_only": str(open_only).lower()})
    return {"alerts": _mine(data.get("alerts", []), await team(db, user))}


async def unlock_requests(db: AsyncSession, user: User, status: str = "pending") -> dict:
    params = {"status": status}
    if user.role != "admin":
        params["manager_id"] = str(user.id)  # the monitoring server's own filter: requests waiting on me
    data = await call("GET", "/api/crm/unlock-requests", params=params)
    return {"requests": _mine(data.get("requests", []), await team(db, user))}


async def decide(db: AsyncSession, user: User, request_id: int, decision: str, comment: str | None) -> dict:
    """Approve or reject an unlock. Checked here (my team) AND on the monitoring server (manager, backup
    approver, or a linked monitoring admin). The approver is always the logged-in person, never the request body."""
    allowed = await team(db, user)
    if allowed is not None:
        waiting = await call("GET", "/api/crm/unlock-requests", params={"status": "pending"})
        req = next((r for r in waiting.get("requests", []) if r.get("id") == request_id), None)
        if req is None or req.get("employee_id") not in allowed:
            raise AppError(403, "not_your_team", "You can only decide unlock requests for people who report to you.")
    try:
        out = await call("POST", f"/api/crm/unlock-requests/{request_id}/decision",
                         body={"decision": decision, "comment": comment}, actor=user)
    except AppError as e:
        if e.code == "monitoring_forbidden":
            raise AppError(403, "not_your_approval",
                           "The monitoring server says you are not this person's approver. An admin needs a "
                           "linked monitoring account to decide for anyone.") from e
        raise
    audit_service.record(db, actor=user, action=f"monitoring.unlock_{decision}", entity_type="unlock_request",
                         entity_id=request_id, after={"comment": comment})
    await db.commit()
    return out


async def daily(db: AsyncSession, user: User, employee_id: str, day: date) -> dict:
    if employee_id != str(user.id):
        if not perms(user) & {VIEW, APPROVE}:
            raise AppError(403, "forbidden", "You can only see your own day.")
        allowed = await team(db, user)
        if allowed is not None and employee_id not in allowed:
            raise AppError(403, "not_your_team", "You can only see people who report to you.")
    return await call("GET", "/api/crm/reports/daily", params={"employee_id": employee_id, "date": day.isoformat()})


# ---------- Pushes from the monitoring server ----------
async def _recipients(db: AsyncSession, alert: dict) -> set[int]:
    approvers = set(await notification_service.users_with(db, APPROVE))
    kind = alert.get("type")
    if kind in TO_MANAGER:
        emp = alert.get("employee_id")
        manager = await db.scalar(select(User.reporting_to).where(User.id == int(emp))) if str(emp).isdigit() else None
        if manager in approvers:
            return {manager}
        return approvers  # no manager who can act: every approver hears it
    if kind in TO_APPROVERS:
        return approvers
    return set()


async def _ring(db: AsyncSession, alerts_in: list[dict]) -> int:
    """Bells for alerts we have not rung yet (a push and the catch-up job may both bring one)."""
    rung = 0
    for a in alerts_in:
        if not isinstance(a.get("id"), int):
            continue
        new = await db.scalar(pg_insert(MonitoringAlertSeen).values(alert_id=a["id"])
                              .on_conflict_do_nothing(index_elements=["alert_id"]).returning(MonitoringAlertSeen.alert_id))
        if new is None:
            continue
        who = await _recipients(db, a)
        if who and a.get("type") in TITLES:
            name = a.get("name") or "Someone"
            notification_service.notify(db, who, f"monitoring.{a['type']}", TITLES[a["type"]].format(name=name),
                                        "Open Laptop monitoring to see it and decide.", PAGE)
            rung += 1
    return rung


async def handle_push(db: AsyncSession, body: dict) -> dict:
    alerts_in = [a for a in body.get("alerts") or [] if isinstance(a, dict)]
    rung = await _ring(db, alerts_in)
    await db.commit()
    for what, key in (("alerts", "alerts"), ("live", "devices"), ("unlock", "unlock_requests")):
        if body.get(key):
            publish(what)
    if rung:
        publish("bell")
    return {"rung": rung}


@job("monitoring_alerts_catchup", any_time=True, module="monitoring")
async def alerts_catchup(db: AsyncSession) -> dict:
    """Safety net for a push that failed: read the last few minutes of alerts and ring what was missed."""
    if not settings.MONITORING_BASE_URL or not settings.MONITORING_API_KEY:
        return {"skipped": "not set up"}
    now = datetime.now(timezone.utc)
    state = await db.get(MonitoringLinkState, "alerts_checked_at")
    since = datetime.fromisoformat(state.value) if state and state.value else now - timedelta(minutes=10)
    since -= timedelta(seconds=cfg().monitoring_link.feed_overlap_seconds)  # repeats are fine (alert ids)
    try:
        data = await call("GET", "/api/crm/alerts", params={"since": since.isoformat()})
    except AppError:
        return {"skipped": "monitoring unreachable"}
    rung = await _ring(db, data.get("alerts", []))
    if state is None:
        db.add(MonitoringLinkState(key="alerts_checked_at", value=now.isoformat()))
    else:
        state.value = now.isoformat()
    keep = timedelta(days=cfg().monitoring_link.keep_events_days)
    await db.execute(delete(MonitoringAlertSeen).where(MonitoringAlertSeen.seen_at < now - keep))
    await db.commit()
    if rung:
        publish("bell")
        publish("alerts")
    return {"rung": rung}


# ---------- The live stream to open monitoring tabs ----------
_listeners: set[asyncio.Queue] = set()  # one per open tab (this API runs one worker, so memory is enough)


def publish(what: str) -> None:
    """Tell every open monitoring tab that `what` changed (no data: each tab reloads what it may see)."""
    for q in list(_listeners):
        try:
            q.put_nowait(what)
        except asyncio.QueueFull:
            pass  # a stuck tab: it reloads everything on its next page refresh anyway


def listeners() -> int:
    return len(_listeners)


async def stream(request: Request) -> AsyncIterator[str]:
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _listeners.add(q)
    started = asyncio.get_running_loop().time()
    try:
        c = cfg().monitoring_link
        yield f"event: hello\ndata: {json.dumps({'refresh_seconds': c.page_refresh_seconds})}\n\n"
        while asyncio.get_running_loop().time() - started < STREAM_MAX.total_seconds():
            try:
                what = await asyncio.wait_for(q.get(), timeout=cfg().monitoring_link.stream_ping_seconds)
            except TimeoutError:
                if await request.is_disconnected():
                    break
                yield ": ping\n\n"  # keeps proxies from closing a quiet connection
                continue
            yield f"event: changed\ndata: {json.dumps({'what': what})}\n\n"
    finally:
        _listeners.discard(q)
