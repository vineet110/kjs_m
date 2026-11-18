"""Work pages (Team work / My work): permissions, own-data only, timeline order and filters, IST days,
range limit, one audit row per viewer per day, area switch, config/monitoring.ini."""
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.core.config import ini
from app.core.database import AsyncSessionLocal
from app.models.audit import AuditLog
from app.models.chat import ChatChannel, ChatMessage
from app.models.lead import Lead, LeadNote
from app.models.task import Task
from app.models.user import User
from app.services import attendance_service as att
from app.services import work_service
from tests.conftest import login, make_user

DAY = date(2026, 11, 10)


def ist(d: date, hhmm: str) -> datetime:
    return att.to_utc(d, hhmm)


@pytest.fixture
def setting(monkeypatch):
    """setting("monitoring", "max_range_days", 7): one config value for one test."""
    def set_(section, key, value):
        monkeypatch.setenv(f"KJS__{section.upper()}__{key.upper()}", str(value))
        ini.reload_now()
    yield set_
    monkeypatch.undo()
    ini.reload_now()


async def _id(email: str) -> int:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(User.id).where(User.email == email))


async def _seed(uid: int, other: int, day: date = DAY) -> None:
    """One of each timeline type for `uid` on `day`, plus a call by someone else."""
    async with AsyncSessionLocal() as db:
        lead = Lead(source="internal", name="Shree Textiles", company="Shree", consent=True,
                    consent_at=datetime.now(timezone.utc))
        db.add(lead)
        await db.flush()
        db.add_all([
            LeadNote(lead_id=lead.id, user_id=uid, kind="call", text="Wants 200 m sample", created_at=ist(day, "12:02")),
            LeadNote(lead_id=lead.id, user_id=uid, kind="email", text="Quotation sent", created_at=ist(day, "10:48")),
            LeadNote(lead_id=lead.id, user_id=uid, kind="outcome", text="quote_sent", created_at=ist(day, "12:10")),
            LeadNote(lead_id=lead.id, user_id=other, kind="call", text="NOT MINE", created_at=ist(day, "11:00")),
            Task(title="Follow up Mehta", assignee_id=uid, status="done", outcome="Spoke to Mr Mehta",
                 completed_at=ist(day, "10:20")),
            Task(title="Open task", assignee_id=uid, status="todo"),
        ])
        dm = ChatChannel(kind="dm", dm_key=f"{min(uid, other)}:{max(uid, other)}")
        db.add(dm)
        await db.flush()
        db.add_all([
            ChatMessage(channel_id=dm.id, sender_id=uid, body="Sample goes Friday", created_at=ist(day, "11:30")),
            ChatMessage(channel_id=dm.id, sender_id=uid, body="gone", created_at=ist(day, "11:31"),
                        deleted_at=ist(day, "11:32")),
        ])
        await db.commit()
        u = await db.get(User, uid)
        await att.check_in(db, u, now=ist(day, "09:02"))


async def _admin_and_staff(client):
    await make_user("admin@kjsindia.com", role="admin")
    await make_user("ravi@kjsindia.com")
    await make_user("priya@kjsindia.com")
    ravi, priya = await _id("ravi@kjsindia.com"), await _id("priya@kjsindia.com")
    await _seed(ravi, priya)
    return ravi, priya


# ---------- Permissions ----------
async def test_team_routes_need_monitor_view(client):
    ravi, _ = await _admin_and_staff(client)
    await login(client, "priya@kjsindia.com")
    for path in ("/api/v1/work/team", f"/api/v1/work/{ravi}/overview", f"/api/v1/work/{ravi}/timeline",
                 f"/api/v1/work/{ravi}/tasks", f"/api/v1/work/{ravi}/attendance"):
        r = await client.get(path)
        assert r.status_code == 403 and r.json()["code"] == "forbidden", path


async def test_admin_and_ticked_employee_may_see_team(client):
    ravi, _ = await _admin_and_staff(client)
    await make_user("lead@kjsindia.com", permissions=["leads.view", "monitor.view"])
    for who in ("admin@kjsindia.com", "lead@kjsindia.com"):
        await login(client, who)
        r = await client.get("/api/v1/work/team", params={"day": DAY.isoformat()})
        assert r.status_code == 200, r.text
        row = next(x for x in r.json()["rows"] if x["user_id"] == ravi)
        assert (row["calls"], row["emails"], row["outcomes"], row["tasks_done"], row["chat"]) == (1, 1, 1, 1, 1)
        assert row["check_in"] == "09:02"
        assert r.json()["refresh_seconds"] == 30


async def test_my_work_is_always_my_own(client):
    ravi, priya = await _admin_and_staff(client)
    await login(client, "priya@kjsindia.com")
    r = await client.get("/api/v1/work/me/timeline", params={"from": DAY.isoformat()})
    texts = [i["text"] for i in r.json()["items"]]
    assert texts == ["NOT MINE"]  # priya's own call only, nothing of ravi's
    r = await client.get("/api/v1/work/me/overview", params={"from": DAY.isoformat(), "user_id": ravi})
    assert r.json()["user"]["id"] == priya  # an id in the request is ignored


async def test_unknown_person_is_404(client):
    await _admin_and_staff(client)
    await login(client, "admin@kjsindia.com")
    assert (await client.get("/api/v1/work/99999/overview")).status_code == 404


# ---------- Timeline ----------
async def test_timeline_mixes_sources_newest_first_with_full_text(client):
    ravi, priya = await _admin_and_staff(client)
    await login(client, "admin@kjsindia.com")
    r = await client.get(f"/api/v1/work/{ravi}/timeline", params={"from": DAY.isoformat()})
    items = r.json()["items"]
    assert [i["kind"] for i in items] == ["outcome", "call", "chat", "email", "task", "attendance"]
    assert [i["time"] for i in items] == ["12:10", "12:02", "11:30", "10:48", "10:20", "09:02"]
    call = items[1]
    assert call["text"] == "Wants 200 m sample" and "Shree Textiles" in call["title"]
    assert items[2]["title"] == "Chat · Direct message to priya"  # deleted message left out
    assert "Spoke to Mr Mehta" in items[4]["text"]
    assert r.json()["next_before"] is None


async def test_timeline_filter_by_kind(client):
    ravi, _ = await _admin_and_staff(client)
    await login(client, "admin@kjsindia.com")
    r = await client.get(f"/api/v1/work/{ravi}/timeline", params={"from": DAY.isoformat(), "kinds": "call,task"})
    assert [i["kind"] for i in r.json()["items"]] == ["call", "task"]
    r = await client.get(f"/api/v1/work/{ravi}/timeline", params={"kinds": "screenshots"})
    assert r.status_code == 400 and r.json()["code"] == "bad_kind"


async def test_ist_day_boundaries():
    """00:30 IST on the 11th is 19:00 UTC on the 10th: it belongs to the 11th."""
    await make_user("e@kjsindia.com")
    uid = await _id("e@kjsindia.com")
    async with AsyncSessionLocal() as db:
        lead = Lead(source="internal", name="L", consent=True, consent_at=datetime.now(timezone.utc))
        db.add(lead)
        await db.flush()
        db.add(LeadNote(lead_id=lead.id, user_id=uid, kind="call", text="late", created_at=ist(DAY + timedelta(days=1), "00:30")))
        await db.commit()
        assert (await work_service.timeline(db, uid, DAY, DAY))["items"] == []
        nxt = (await work_service.timeline(db, uid, DAY + timedelta(days=1), DAY + timedelta(days=1)))["items"]
        assert [i["text"] for i in nxt] == ["late"] and nxt[0]["day"] == DAY + timedelta(days=1)


async def test_timeline_pages_follow_on_without_gaps(setting):
    setting("monitoring", "timeline_page_size", 20)
    await make_user("e@kjsindia.com")
    uid = await _id("e@kjsindia.com")
    async with AsyncSessionLocal() as db:
        lead = Lead(source="internal", name="L", consent=True, consent_at=datetime.now(timezone.utc))
        db.add(lead)
        await db.flush()
        for n in range(45):  # pairs share a time: a page must never cut a pair in half and lose one
            db.add(LeadNote(lead_id=lead.id, user_id=uid, kind="note", text=str(n),
                            created_at=ist(DAY, "09:00") + timedelta(minutes=n // 2)))
        await db.commit()
        seen, before = [], None
        while True:
            page = await work_service.timeline(db, uid, DAY, DAY, before=before)
            seen += [i["text"] for i in page["items"]]
            before = page["next_before"]
            if before is None:
                break
    assert sorted(seen, key=int) == [str(n) for n in range(45)]  # every one, none twice


# ---------- Range limit (config/monitoring.ini) ----------
async def test_range_limit_comes_from_config(client, setting):
    ravi, _ = await _admin_and_staff(client)
    await login(client, "admin@kjsindia.com")
    long = {"from": "2026-10-01", "to": "2026-11-10"}  # 41 days
    r = await client.get(f"/api/v1/work/{ravi}/timeline", params=long)
    assert r.status_code == 400 and r.json()["details"]["max_days"] == 31
    setting("monitoring", "max_range_days", 60)
    assert (await client.get(f"/api/v1/work/{ravi}/timeline", params=long)).status_code == 200
    r = await client.get(f"/api/v1/work/{ravi}/timeline", params={"from": "2026-11-10", "to": "2026-11-01"})
    assert r.status_code == 400 and r.json()["code"] == "bad_range"


# ---------- Audit: one row per viewer, per person, per day ----------
async def _views() -> int:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action == "work.viewed"))


async def test_one_audit_row_per_viewer_per_person_per_day(client):
    ravi, priya = await _admin_and_staff(client)
    await login(client, "admin@kjsindia.com")
    for _ in range(3):
        await client.get(f"/api/v1/work/{ravi}/overview")
        await client.get(f"/api/v1/work/{ravi}/timeline")
    assert await _views() == 1
    await client.get(f"/api/v1/work/{priya}/overview")
    assert await _views() == 2  # a different person: a new row
    await login(client, "ravi@kjsindia.com")
    await client.get("/api/v1/work/me/overview")
    assert await _views() == 2  # own page: no row


async def test_yesterdays_view_does_not_count_today(client):
    ravi, _ = await _admin_and_staff(client)
    admin = await _id("admin@kjsindia.com")
    async with AsyncSessionLocal() as db:
        db.add(AuditLog(actor_id=admin, actor_label="Admin", action="work.viewed", entity_type="user",
                        entity_id=str(ravi), at=datetime.now(timezone.utc) - timedelta(days=1)))
        await db.commit()
    await login(client, "admin@kjsindia.com")
    await client.get(f"/api/v1/work/{ravi}/overview")
    assert await _views() == 2


# ---------- Tasks and attendance tabs ----------
async def test_tasks_tab_open_plus_done_in_range(client):
    ravi, _ = await _admin_and_staff(client)
    await login(client, "admin@kjsindia.com")
    titles = [t["title"] for t in (await client.get(f"/api/v1/work/{ravi}/tasks", params={"from": DAY.isoformat()})).json()]
    assert titles == ["Open task", "Follow up Mehta"]
    later = (DAY + timedelta(days=3)).isoformat()
    titles = [t["title"] for t in (await client.get(f"/api/v1/work/{ravi}/tasks", params={"from": later})).json()]
    assert titles == ["Open task"]


async def test_attendance_tab_is_the_month_view(client):
    ravi, _ = await _admin_and_staff(client)
    await login(client, "admin@kjsindia.com")
    r = await client.get(f"/api/v1/work/{ravi}/attendance", params={"year": 2026, "month": 11})
    assert r.status_code == 200
    r = await client.get(f"/api/v1/work/{ravi}/overview", params={"from": DAY.isoformat()})
    assert r.json()["totals"]["days_present"] == 1


# ---------- Area switch ----------
async def test_area_off_hides_every_route(client, setting):
    ravi, _ = await _admin_and_staff(client)
    await login(client, "admin@kjsindia.com")
    setting("modules", "monitoring", "off")
    for path in ("/api/v1/work/team", f"/api/v1/work/{ravi}/timeline", "/api/v1/work/me/overview"):
        assert (await client.get(path)).json()["code"] == "module_off", path
    me = (await client.get("/api/v1/auth/me")).json()
    assert me["modules"]["monitoring"] is False
