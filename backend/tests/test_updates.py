"""GET /employee/updates (the portal's 30-second check) and the bell's unread-only list."""
from datetime import datetime, timezone

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.lead import Lead
from app.models.user import User
from app.services import notification_service
from tests.conftest import HDR, login, make_user

URL = "/api/v1/employee/updates"


async def _uid(email: str) -> int:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(User.id).where(User.email == email))


async def _lead(source: str, status: str = "new", assigned_to: int | None = None):
    async with AsyncSessionLocal() as db:
        db.add(Lead(source=source, name=f"Buyer {source}", consent=True, consent_at=datetime.now(timezone.utc),
                    status=status, assigned_to=assigned_to))
        await db.commit()


async def _notify(email: str, n: int):
    uid = await _uid(email)
    async with AsyncSessionLocal() as db:
        for i in range(n):
            notification_service.notify(db, [uid], "test", f"Note {i}")
        await db.commit()


async def test_counters_for_a_plain_employee(client):
    await make_user("staff@kjs.test")
    await make_user("other@kjs.test")
    me, other = await _uid("staff@kjs.test"), await _uid("other@kjs.test")
    await _lead("koko")                       # unassigned: I may pick it up -> counts
    await _lead("internal", assigned_to=me)   # mine -> counts
    await _lead("enquiry_form", assigned_to=other)  # someone else's -> not mine to see
    await _lead("koko", status="contacted")   # not new any more -> doesn't count
    await _notify("staff@kjs.test", 2)
    await login(client, "staff@kjs.test")
    r = (await client.get(URL, headers=HDR)).json()
    assert r["notifications"] == 2
    assert r["approvals"] is None  # nothing for them to approve
    assert r["leads"] == {"all": 2, "koko": 1, "internal": 1}
    assert r["chat"] == 0


async def test_view_all_sees_every_new_lead_and_approver_sees_waiting_sign_ups(client):
    await make_user("approver@kjs.test", permissions=["leads.view", "leads.view_all", "staff.approve"])
    await make_user("someone@kjs.test")
    await _lead("enquiry_form", assigned_to=await _uid("someone@kjs.test"))
    await _lead("koko")
    await make_user("pending@kjs.test", status="pending")
    await login(client, "approver@kjs.test")
    r = (await client.get(URL, headers=HDR)).json()
    assert r["leads"]["all"] == 2
    assert r["approvals"] == 1


async def test_counter_changes_when_something_happens(client):
    """What the page relies on: a new notification moves the number, reading it brings it back."""
    await make_user("staff@kjs.test")
    await login(client, "staff@kjs.test")
    assert (await client.get(URL, headers=HDR)).json()["notifications"] == 0
    await _notify("staff@kjs.test", 1)
    assert (await client.get(URL, headers=HDR)).json()["notifications"] == 1
    await client.post("/api/v1/employee/notifications/read", headers=HDR, json={})
    assert (await client.get(URL, headers=HDR)).json()["notifications"] == 0


async def test_bell_unread_only_drops_opened_notifications(client):
    await make_user("staff@kjs.test")
    await _notify("staff@kjs.test", 3)
    await login(client, "staff@kjs.test")
    items = (await client.get("/api/v1/employee/notifications?unread=1", headers=HDR)).json()["items"]
    assert len(items) == 3
    await client.post("/api/v1/employee/notifications/read", headers=HDR, json={"ids": [items[0]["id"]]})
    after = (await client.get("/api/v1/employee/notifications?unread=1", headers=HDR)).json()
    assert len(after["items"]) == 2 and after["unread"] == 2
    assert items[0]["id"] not in [n["id"] for n in after["items"]]
    everything = (await client.get("/api/v1/employee/notifications", headers=HDR)).json()["items"]
    assert len(everything) == 3  # without ?unread the old list still shows all


async def test_updates_needs_login():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.get(URL, headers=HDR)).status_code == 401
