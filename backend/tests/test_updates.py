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
    assert {k: v for k, v in r["leads"].items() if k != "changed"} == {"all": 2, "koko": 1, "internal": 1}
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


async def test_leads_changed_moves_on_status_note_and_handover(client):
    """The lead lists reload on `changed`, not on the counts: a lead leaving "new" while another arrives
    keeps every count the same (CodeRabbit on #76). It must move on each kind of change."""
    await make_user("staff@kjs.test")
    await make_user("other@kjs.test")
    me = await _uid("staff@kjs.test")
    await _lead("koko", assigned_to=me)
    async with AsyncSessionLocal() as db:
        lead_id = await db.scalar(select(Lead.id))
    await login(client, "staff@kjs.test")
    changed = lambda: client.get(URL, headers=HDR)  # noqa: E731
    seen = [(await changed()).json()["leads"]["changed"]]
    assert seen[0]
    steps = [
        ("status", client.patch(f"/api/v1/employee/leads/{lead_id}", headers=HDR, json={"status": "contacted"})),
        ("note", client.post(f"/api/v1/employee/leads/{lead_id}/notes", headers=HDR, json={"kind": "note", "text": "Asked for samples"})),
        ("handover", client.post(f"/api/v1/employee/leads/{lead_id}/handover", headers=HDR, json={"user_id": await _uid("other@kjs.test")})),
    ]
    for name, request in steps:
        r = await request
        assert r.status_code == 204, (name, r.text)
        now = (await changed()).json()["leads"]["changed"]
        assert now != seen[-1], f"{name} did not move leads.changed"
        seen.append(now)


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


async def test_chat_last_moves_on_a_new_message_even_in_a_muted_chat(client):
    """The chat page catches up on `chat_last` (newest message in my chats), not on the unread number, which
    leaves muted chats out and moves when I read."""
    await make_user("staff@kjs.test")
    await make_user("a@kjs.test")
    await make_user("b@kjs.test")
    await login(client, "staff@kjs.test")
    ids = [await _uid("a@kjs.test"), await _uid("b@kjs.test")]
    ch = (await client.post("/api/v1/chat/channels", headers=HDR,
                            json={"kind": "group", "name": "G", "description": "", "is_private": True, "member_ids": ids})).json()
    async with AsyncSessionLocal() as db:  # mute it for me
        from app.models.chat import ChatMember
        m = await db.scalar(select(ChatMember).where(ChatMember.channel_id == ch["id"], ChatMember.user_id == await _uid("staff@kjs.test")))
        m.muted = True
        await db.commit()
    before = (await client.get(URL, headers=HDR)).json()["chat_last"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        await login(other, "a@kjs.test")
        r = await other.post(f"/api/v1/chat/channels/{ch['id']}/messages", headers=HDR, json={"body": "hello", "mention_ids": []})
        assert r.status_code in (200, 201), r.text
    after = (await client.get(URL, headers=HDR)).json()
    assert after["chat_last"] != before and after["chat"] == 0  # muted: no unread badge, but the page still catches up
