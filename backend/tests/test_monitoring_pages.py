"""Laptop monitoring pages (Phase 3): who sees whom, unlock decisions, the bell from monitoring pushes, the
catch-up job and the live stream. The monitoring server is faked (httpx.MockTransport): no real calls."""
import asyncio
import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app.core.config import ini, settings
from app.core.database import AsyncSessionLocal
from app.models.audit import AuditLog
from app.models.notification import Notification
from app.models.user import User
from app.services import monitoring_link_service as link
from app.services import monitoring_service as svc
from tests.conftest import HDR, login, make_user

FEED_KEY = "k" * 40
PUSH = "/api/v1/integrations/monitoring/api/monitoring/push"


class FakeMonitoring:
    """Answers like monitering/backend/app/api/crm.py."""

    def __init__(self):
        self.calls: list[httpx.Request] = []
        self.employees: list[dict] = []
        self.requests: list[dict] = []
        self.alerts: list[dict] = []
        self.down = False
        self.decision_status = 200

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("monitoring down")
        assert request.headers["x-api-key"] == "mon-key"
        self.calls.append(request)
        path = request.url.path
        if path == "/api/crm/live-status":
            return httpx.Response(200, json={"employees": self.employees})
        if path == "/api/crm/alerts":
            return httpx.Response(200, json={"alerts": self.alerts})
        if path == "/api/crm/unlock-requests":
            return httpx.Response(200, json={"requests": self.requests})
        if path.startswith("/api/crm/unlock-requests/") and path.endswith("/decision"):
            if self.decision_status != 200:
                return httpx.Response(self.decision_status, json={"detail": "not allowed to decide for this employee"})
            return httpx.Response(200, json={"id": int(path.split("/")[4]), "decision": json.loads(request.content)["decision"]})
        if path == "/api/crm/reports/daily":
            return httpx.Response(200, json={"employee_id": request.url.params["employee_id"], "worked_min": 300})
        return httpx.Response(404, json={"detail": "no such path"})


@pytest.fixture
def mon(monkeypatch):
    fake = FakeMonitoring()
    monkeypatch.setattr(settings, "MONITORING_BASE_URL", "http://mon-api:8000")
    monkeypatch.setattr(settings, "MONITORING_API_KEY", "mon-key")
    monkeypatch.setattr(settings, "MONITORING_FEED_KEY", FEED_KEY)
    monkeypatch.setattr(link, "_client", httpx.AsyncClient(transport=httpx.MockTransport(fake), base_url="http://mon-api:8000",
                                                           headers={"X-Api-Key": "mon-key"}))
    yield fake


async def _person(email, **fields) -> User:
    await make_user(email, permissions=fields.pop("permissions", ["leads.view"]))
    async with AsyncSessionLocal() as db:
        u = await db.scalar(select(User).where(User.email == email))
        for k, v in fields.items():
            setattr(u, k, v)
        await db.commit()
        await db.refresh(u)
        return u


async def _team():
    """A manager (view + approve) with one report, and someone from another team."""
    boss = await _person("boss@kjsindia.com", permissions=["leads.view", "monitoring.view", "monitoring.approve"])
    mine = await _person("mine@kjsindia.com", reporting_to=boss.id)
    other = await _person("other@kjsindia.com")
    return boss, mine, other


def _row(u: User, **extra) -> dict:
    return {"employee_id": str(u.id), "name": u.name, **extra}


# ---------- Who sees whom ----------
async def test_a_manager_sees_only_their_team(client, mon):
    boss, mine, other = await _team()
    mon.employees = [_row(mine, status="WORKING"), _row(other, status="OFF_DUTY")]
    await login(client, "boss@kjsindia.com")
    r = await client.get("/api/v1/monitoring/live")
    assert r.status_code == 200 and [e["employee_id"] for e in r.json()["employees"]] == [str(mine.id)]


async def test_an_admin_sees_everyone(client, mon):
    _, mine, other = await _team()
    mon.employees = [_row(mine), _row(other)]
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    r = await client.get("/api/v1/monitoring/live")
    assert len(r.json()["employees"]) == 2


async def test_staff_without_the_permission_are_refused(client, mon):
    await _team()
    await login(client, "mine@kjsindia.com")
    for path in ("/api/v1/monitoring/live", "/api/v1/monitoring/alerts", "/api/v1/monitoring/unlock-requests"):
        assert (await client.get(path)).status_code == 403, path
    r = await client.post("/api/v1/monitoring/unlock-requests/1/decision", headers=HDR, json={"decision": "approved"})
    assert r.status_code == 403
    assert mon.calls == []  # refused before the monitoring server was asked anything


async def test_area_off_is_404(client, mon, monkeypatch):
    await _team()
    monkeypatch.setenv("KJS__MODULES__MONITORING", "off")
    ini.reload_now()
    await login(client, "boss@kjsindia.com")
    r = await client.get("/api/v1/monitoring/live")
    assert r.status_code == 404 and r.json()["code"] == "module_off"


async def test_not_logged_in_is_401(client, mon):
    assert (await client.get("/api/v1/monitoring/live")).status_code == 401


# ---------- Unlock decisions ----------
async def test_a_manager_approves_their_report_and_it_is_audited(client, mon):
    boss, mine, _ = await _team()
    mon.requests = [{"id": 7, **_row(mine), "decision": None}]
    await login(client, "boss@kjsindia.com")
    waiting = (await client.get("/api/v1/monitoring/unlock-requests")).json()["requests"]
    assert [w["id"] for w in waiting] == [7]
    assert mon.calls[-1].url.params["manager_id"] == str(boss.id)
    r = await client.post("/api/v1/monitoring/unlock-requests/7/decision", headers=HDR,
                          json={"decision": "approved", "comment": "in a meeting", "actor": "999"})
    assert r.status_code == 200, r.text
    decision_call = mon.calls[-1]
    assert decision_call.headers["x-actor"] == str(boss.id)  # the logged-in person, never the body
    assert json.loads(decision_call.content) == {"decision": "approved", "comment": "in a meeting"}
    async with AsyncSessionLocal() as db:
        row = await db.scalar(select(AuditLog).where(AuditLog.action == "monitoring.unlock_approved"))
    assert row is not None


async def test_a_manager_cannot_decide_for_another_team(client, mon):
    _, _, other = await _team()
    mon.requests = [{"id": 8, **_row(other), "decision": None}]
    await login(client, "boss@kjsindia.com")
    r = await client.post("/api/v1/monitoring/unlock-requests/8/decision", headers=HDR, json={"decision": "approved"})
    assert r.status_code == 403 and r.json()["code"] == "not_your_team"
    assert not any(c.url.path.endswith("/decision") for c in mon.calls)


async def test_the_monitoring_servers_refusal_is_explained(client, mon):
    await make_user("admin@kjsindia.com", role="admin")
    mon.decision_status = 403  # an admin without a linked monitoring account
    await login(client, "admin@kjsindia.com")
    r = await client.post("/api/v1/monitoring/unlock-requests/9/decision", headers=HDR, json={"decision": "rejected"})
    assert r.status_code == 403 and r.json()["code"] == "not_your_approval"


async def test_a_bad_decision_value_is_422(client, mon):
    await _team()
    await login(client, "boss@kjsindia.com")
    r = await client.post("/api/v1/monitoring/unlock-requests/1/decision", headers=HDR, json={"decision": "maybe"})
    assert r.status_code == 422


# ---------- Day reports ----------
async def test_everyone_sees_their_own_day_but_not_others(client, mon):
    _, mine, other = await _team()
    await login(client, "mine@kjsindia.com")
    r = await client.get("/api/v1/monitoring/me/today")
    assert r.status_code == 200 and r.json()["employee_id"] == str(mine.id)
    r = await client.get("/api/v1/monitoring/reports/daily", params={"employee_id": str(other.id), "date": "2026-11-27"})
    assert r.status_code == 403


async def test_a_manager_sees_a_reports_day_but_not_another_teams(client, mon):
    _, mine, other = await _team()
    await login(client, "boss@kjsindia.com")
    ok = await client.get("/api/v1/monitoring/reports/daily", params={"employee_id": str(mine.id), "date": "2026-11-27"})
    no = await client.get("/api/v1/monitoring/reports/daily", params={"employee_id": str(other.id), "date": "2026-11-27"})
    assert ok.status_code == 200 and no.status_code == 403


# ---------- When the monitoring server is away ----------
async def test_monitoring_down_is_a_clear_503(client, mon):
    await _team()
    mon.down = True
    await login(client, "boss@kjsindia.com")
    r = await client.get("/api/v1/monitoring/live")
    assert r.status_code == 503 and r.json()["code"] == "monitoring_unreachable"


async def test_not_set_up_is_a_clear_503(client, mon, monkeypatch):
    await _team()
    monkeypatch.setattr(settings, "MONITORING_BASE_URL", "")
    await login(client, "boss@kjsindia.com")
    r = await client.get("/api/v1/monitoring/live")
    assert r.status_code == 503 and r.json()["code"] == "monitoring_not_set_up"


# ---------- Pushes from the monitoring server: the bell ----------
def _alert(id_: int, kind: str, u: User | None) -> dict:
    return {"id": id_, "type": kind, "created_at": "2026-11-28T09:00:00+00:00",
            "employee_id": str(u.id) if u else None, "name": u.name if u else None, "data": {}}


async def _bells(user_id: int) -> list[Notification]:
    async with AsyncSessionLocal() as db:
        return list((await db.scalars(select(Notification).where(Notification.user_id == user_id))).all())


async def test_a_lock_request_rings_the_managers_bell_once(client, mon):
    boss, mine, _ = await _team()
    body = {"alerts": [_alert(1, "lock.requested", mine)], "devices": [], "unlock_requests": []}
    for _ in range(2):  # sent twice (a retry, or push + catch-up)
        r = await client.post(PUSH, headers={"x-api-key": FEED_KEY}, json=body)
        assert r.status_code == 200, r.text
    bells = await _bells(boss.id)
    assert len(bells) == 1 and bells[0].kind == "monitoring.lock.requested" and bells[0].link == "/admin/monitoring"
    assert mine.name in bells[0].title


async def test_with_no_manager_who_can_act_every_approver_hears_it(client, mon):
    await _team()
    loner = await _person("loner@kjsindia.com")  # reports to nobody
    await make_user("admin@kjsindia.com", role="admin")
    await client.post(PUSH, headers={"x-api-key": FEED_KEY},
                      json={"alerts": [_alert(2, "lock.requested", loner)]})
    async with AsyncSessionLocal() as db:
        admin = await db.scalar(select(User).where(User.email == "admin@kjsindia.com"))
        boss = await db.scalar(select(User).where(User.email == "boss@kjsindia.com"))
    assert len(await _bells(admin.id)) == 1 and len(await _bells(boss.id)) == 1


async def test_noisy_alerts_ring_no_bell(client, mon):
    boss, mine, _ = await _team()
    await client.post(PUSH, headers={"x-api-key": FEED_KEY},
                      json={"alerts": [_alert(3, "agent.offline", mine), _alert(4, "crm.sync_failed", None)]})
    assert await _bells(boss.id) == []


async def test_the_push_needs_the_key_and_a_sane_body(client, mon):
    assert (await client.post(PUSH, json={"alerts": []})).status_code == 401
    assert (await client.post(PUSH, headers={"x-api-key": "wrong"}, json={})).status_code == 401
    r = await client.post(PUSH, headers={"x-api-key": FEED_KEY}, json={"alerts": [{}] * 501})
    assert r.status_code == 422
    r = await client.post(PUSH, headers={"x-api-key": FEED_KEY}, json={"alerts": "x"})
    assert r.status_code == 422


async def test_the_catch_up_job_rings_what_a_lost_push_missed_once(mon):
    boss, mine, _ = await _team()
    mon.alerts = [_alert(5, "lock.requested", mine)]
    async with AsyncSessionLocal() as db:
        assert (await svc.alerts_catchup(db))["rung"] == 1
    async with AsyncSessionLocal() as db:
        assert (await svc.alerts_catchup(db))["rung"] == 0
    assert len(await _bells(boss.id)) == 1


async def test_the_catch_up_job_waits_quietly_when_monitoring_is_down(mon):
    mon.down = True
    async with AsyncSessionLocal() as db:
        assert (await svc.alerts_catchup(db)) == {"skipped": "monitoring unreachable"}


# ---------- The live stream ----------
async def test_a_push_reaches_open_tabs_at_once(client, mon):
    boss, mine, _ = await _team()
    q: asyncio.Queue = asyncio.Queue()
    svc._listeners.add(q)
    try:
        await client.post(PUSH, headers={"x-api-key": FEED_KEY}, json={
            "alerts": [_alert(6, "lock.requested", mine)], "devices": [{"employee_id": str(mine.id), "state": "LOCKED"}],
            "unlock_requests": [{"id": 1, "employee_id": str(mine.id), "decision": None}]})
        got = set()
        while not q.empty():
            got.add(q.get_nowait())
        assert got == {"alerts", "live", "unlock", "bell"}
    finally:
        svc._listeners.discard(q)


async def test_the_stream_says_hello_then_passes_changes_on():
    class Req:
        async def is_disconnected(self):
            return False

    gen = svc.stream(Req())
    hello = await gen.__anext__()
    assert hello.startswith("event: hello") and '"refresh_seconds": 60' in hello
    nxt = asyncio.ensure_future(gen.__anext__())
    await asyncio.sleep(0)
    svc.publish("unlock")
    assert (await asyncio.wait_for(nxt, 2)) == 'event: changed\ndata: {"what": "unlock"}\n\n'
    await gen.aclose()
    assert svc.listeners() == 0  # a closed tab leaves nothing behind


async def test_the_stream_needs_a_login_and_the_permission(client, mon):
    await _team()
    assert (await client.get("/api/v1/monitoring/stream")).status_code == 401
    await login(client, "mine@kjsindia.com")
    assert (await client.get("/api/v1/monitoring/stream")).status_code == 403


def test_nginx_passes_the_stream_unbuffered():
    conf = (Path(__file__).resolve().parents[2] / "deploy" / "nginx" / "default.conf").read_text(encoding="utf-8")
    block = conf[conf.index("location = /api/v1/monitoring/stream"):]
    block = block[:block.index("}")]
    assert "proxy_buffering off" in block and "proxy_read_timeout" in block
    assert "proxy_set_header" not in block  # would drop the server block's Host / X-Forwarded-For
