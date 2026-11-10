"""Lead SLA timers (working hours only), escalation job, notes, hand-over, notifications."""
from datetime import date, datetime

import pytest
from sqlalchemy import select

from app.core.config import ini
from app.core.database import AsyncSessionLocal
from app.jobs.runner import run_job
from app.models.lead import Lead
from app.models.notification import Notification
from app.models.user import User
from app.services import lead_service
from app.services.attendance_service import to_utc
from tests.conftest import HDR, login, make_user

ENQ = {"name": "Omar", "email": "omar@alnoor.ae", "consent": True, "phone": "+91 98765 43210", "message": "Need 3-in-1 sticks"}


def ist(d: str, hhmm: str) -> datetime:
    return to_utc(date.fromisoformat(d), hhmm)


def test_work_minutes_same_day():
    assert lead_service.add_work_minutes(ist("2026-10-26", "10:00"), 20, set()) == ist("2026-10-26", "10:20")


def test_work_minutes_roll_over_sunday():
    # Sat 18:20 + 20 min: 10 min Saturday (shift ends 18:30), 10 min Monday from 09:30
    assert lead_service.add_work_minutes(ist("2026-10-31", "18:20"), 20, set()) == ist("2026-11-02", "09:40")


def test_work_minutes_night_and_holiday():
    # Sunday night lead, Monday is a holiday -> Tuesday 09:50
    assert lead_service.add_work_minutes(ist("2026-11-01", "23:00"), 20, {date(2026, 11, 2)}) == ist("2026-11-03", "09:50")


def test_sla_states():
    lead = Lead(status="new", created_at=ist("2026-10-26", "10:00"))
    assert lead_service.sla(lead, ist("2026-10-26", "10:05"), set())["sla_state"] == "ok"
    assert lead_service.sla(lead, ist("2026-10-26", "10:17"), set())["sla_state"] == "due_soon"
    late = lead_service.sla(lead, ist("2026-10-26", "10:30"), set())
    assert late["sla_state"] == "overdue" and late["sla_label"] == "Respond overdue by 10 min"
    lead.status = "contacted"
    assert lead_service.sla(lead, ist("2026-10-26", "10:30"), set())["sla_label"] == "Resolve in 30 min"


async def _new_lead(client, created_at: datetime) -> int:
    assert (await client.post("/api/v1/public/leads", json=ENQ, headers=HDR)).status_code == 201
    async with AsyncSessionLocal() as db:
        lead = await db.scalar(select(Lead).order_by(Lead.id.desc()))
        lead.created_at = created_at
        await db.commit()
        return lead.id


async def _user_id(email: str) -> int:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(User.id).where(User.email == email))


@pytest.fixture
def sla_20_60_10(monkeypatch):
    """Pin the SLA numbers so the test does not depend on what config/sla.ini says today."""
    monkeypatch.setenv("KJS__SLA__RESPOND_MINUTES", "20")
    monkeypatch.setenv("KJS__SLA__RESOLVE_MINUTES", "60")
    monkeypatch.setenv("KJS__SLA__ESCALATE_AFTER_MINUTES", "10")
    ini.reload_now()
    yield
    monkeypatch.undo()
    ini.reload_now()


async def test_escalation_once_per_breach(client, sla_20_60_10):
    await make_user("admin@kjsindia.com", role="admin")
    await _new_lead(client, ist("2026-10-26", "10:00"))
    async with AsyncSessionLocal() as db:
        first = await lead_service.sla_check(db, now=ist("2026-10-26", "10:45"))
        await db.commit()
        again = await lead_service.sla_check(db, now=ist("2026-10-26", "10:46"))
        await db.commit()
        later = await lead_service.sla_check(db, now=ist("2026-10-26", "11:20"))  # resolve late too
        await db.commit()
        kinds = (await db.scalars(select(Notification.kind).order_by(Notification.id))).all()
    assert (first["escalated"], again["escalated"], later["escalated"]) == (1, 0, 1)
    assert kinds == ["lead.new", "lead.sla_breach", "lead.sla_breach"]


async def test_logging_a_call_counts_as_response(client):
    await make_user("e@kjsindia.com")
    lead_id = await _new_lead(client, ist("2026-10-26", "10:00"))
    await login(client, "e@kjsindia.com")
    r = await client.post(f"/api/v1/employee/leads/{lead_id}/notes", json={"kind": "call", "text": "Called, wants samples"}, headers=HDR)
    assert r.status_code == 204
    lead = (await client.get("/api/v1/employee/leads")).json()[0]
    assert lead["status"] == "contacted" and lead["responded_at"] and lead["owner_name"] == "e"
    assert lead["note_count"] == 1
    notes = (await client.get(f"/api/v1/employee/leads/{lead_id}/notes")).json()
    assert notes[0]["kind"] == "call" and notes[0]["user_name"] == "e"


async def test_close_with_outcome(client):
    await make_user("e@kjsindia.com")
    lead_id = await _new_lead(client, ist("2026-10-26", "10:00"))
    await login(client, "e@kjsindia.com")
    r = await client.patch(f"/api/v1/employee/leads/{lead_id}", json={"status": "closed", "outcome": "quote_sent"}, headers=HDR)
    assert r.status_code == 204
    lead = (await client.get("/api/v1/employee/leads")).json()[0]
    assert (lead["sla_state"], lead["outcome"]) == ("done", "quote_sent") and lead["resolved_at"]


async def test_handover_notifies_colleague_and_hides_lead(client):
    await make_user("a@kjsindia.com")
    await make_user("b@kjsindia.com")
    lead_id = await _new_lead(client, ist("2026-10-26", "10:00"))
    await login(client, "a@kjsindia.com")
    r = await client.post(f"/api/v1/employee/leads/{lead_id}/handover", json={"user_id": await _user_id("b@kjsindia.com")}, headers=HDR)
    assert r.status_code == 204
    assert (await client.get("/api/v1/employee/leads")).json() == []  # it is b's lead now
    assert (await client.get(f"/api/v1/employee/leads/{lead_id}/notes")).status_code == 404

    await login(client, "b@kjsindia.com")
    bell = (await client.get("/api/v1/employee/notifications")).json()
    assert bell["unread"] == 1 and "assigned to you" in bell["items"][0]["title"]
    await client.post("/api/v1/employee/notifications/read", json={}, headers=HDR)
    assert (await client.get("/api/v1/employee/notifications")).json()["unread"] == 0


async def test_admin_leads_and_reassign_need_view_all(client):
    await make_user("e@kjsindia.com")
    lead_id = await _new_lead(client, ist("2026-10-19", "10:00"))  # in the past, so overdue now
    await login(client, "e@kjsindia.com")
    assert (await client.get("/api/v1/admin/leads")).status_code == 403
    assert (await client.post(f"/api/v1/admin/leads/{lead_id}/assign", json={"user_id": 1}, headers=HDR)).status_code == 403

    await make_user("m@kjsindia.com", permissions=["leads.view", "leads.view_all"])
    await login(client, "m@kjsindia.com")
    rows = (await client.get("/api/v1/admin/leads?sla=overdue")).json()
    assert [r["id"] for r in rows] == [lead_id]
    r = await client.post(f"/api/v1/admin/leads/{lead_id}/assign", json={"user_id": await _user_id("e@kjsindia.com")}, headers=HDR)
    assert r.status_code == 204
    assert (await client.get("/api/v1/admin/sla")).json()["respond_minutes"] == 20


async def test_assign_to_disabled_user_rejected(client):
    await make_user("m@kjsindia.com", permissions=["leads.view", "leads.view_all"])
    await make_user("gone@kjsindia.com", status="disabled")
    lead_id = await _new_lead(client, ist("2026-10-26", "10:00"))
    await login(client, "m@kjsindia.com")
    r = await client.post(f"/api/v1/admin/leads/{lead_id}/assign", json={"user_id": await _user_id("gone@kjsindia.com")}, headers=HDR)
    assert r.status_code == 422


async def test_send_emails_job_skips_without_smtp(client):
    await make_user("admin@kjsindia.com", role="admin")
    await _new_lead(client, ist("2026-10-26", "10:00"))
    assert await run_job("send_emails") == {"sent": 0, "skipped": 1, "failed": 0}


async def test_weekly_counts_for_overview_trend(client):
    # Rolling windows from "now": 2 leads in the last 7 days, 1 in the 7 days before, 1 older (not counted)
    now = ist("2026-11-03", "12:00")
    for d in ("2026-11-02", "2026-10-28", "2026-10-25", "2026-10-10"):
        await _new_lead(client, ist(d, "10:00"))
    async with AsyncSessionLocal() as db:
        assert await lead_service.weekly_counts(db, now=now) == (2, 1)
