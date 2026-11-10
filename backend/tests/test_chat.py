"""KJS Chat, day 1 (migration 0020): channels, group chats, DMs and members.
Non-members get 404; one DM per pair (even on two clicks at once); archived chats are read-only;
owner rules; the last owner / last person leaving; removals audited."""
import asyncio

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.main import app
from app.models.audit import AuditLog
from app.models.chat import ChatChannel
from app.models.user import User
from tests.conftest import HDR, login, make_user

C = "/api/v1/chat"


async def _team(*names: str) -> dict[str, int]:
    for n in names:
        await make_user(f"{n}@kjsindia.com")
    async with AsyncSessionLocal() as db:
        rows = await db.execute(select(User.name, User.id))
        return {n: i for n, i in rows.all() if n in names}


async def _channel(client, **body) -> dict:
    r = await client.post(f"{C}/channels", json={"name": "sales"} | body, headers=HDR)
    assert r.status_code == 201, r.text
    return r.json()


async def _actions(action: str) -> list[AuditLog]:
    async with AsyncSessionLocal() as db:
        return list((await db.scalars(select(AuditLog).where(AuditLog.action == action))).all())


async def test_needs_login(client):
    assert (await client.get(f"{C}/channels")).status_code == 401


async def test_create_channel_and_list_it(client):
    ids = await _team("asha", "ravi", "meena")
    await login(client, "asha@kjsindia.com")
    ch = await _channel(client, description="Sales team", member_ids=[ids["ravi"], ids["asha"], ids["ravi"]])
    assert ch["kind"] == "channel" and ch["title"] == "sales" and ch["my_role"] == "owner"
    # me first (owner), duplicates and my own id in member_ids are ignored
    assert [(m["name"], m["role"]) for m in ch["members"]] == [("asha", "owner"), ("ravi", "member")]

    await login(client, "ravi@kjsindia.com")
    mine = (await client.get(f"{C}/channels")).json()
    assert [(c["title"], c["my_role"], c["member_count"]) for c in mine] == [("sales", "member", 2)]
    await login(client, "meena@kjsindia.com")
    assert (await client.get(f"{C}/channels")).json() == []


async def test_create_checks_name_people_and_active_users(client):
    ids = await _team("asha", "ravi", "meena", "gone")
    async with AsyncSessionLocal() as db:
        (await db.get(User, ids["gone"])).status = "disabled"
        await db.commit()
    await login(client, "asha@kjsindia.com")
    r = await client.post(f"{C}/channels", json={"name": " x "}, headers=HDR)
    assert r.status_code == 422 and r.json()["code"] == "name_required"
    r = await client.post(f"{C}/channels", json={"kind": "group", "member_ids": [ids["ravi"]]}, headers=HDR)
    assert r.status_code == 422 and r.json()["code"] == "too_few_people"
    r = await client.post(f"{C}/channels", json={"name": "ops", "member_ids": [ids["gone"], 999]}, headers=HDR)
    assert r.status_code == 422 and r.json()["details"]["user_ids"] == [ids["gone"], 999]
    assert (await client.post(f"{C}/channels", json={"kind": "dm"}, headers=HDR)).status_code == 422

    g = await _channel(client, kind="group", name="", member_ids=[ids["ravi"], ids["meena"]])
    assert g["title"] == "ravi, meena" and g["is_private"] is True


async def test_non_members_get_404_everywhere(client):
    ids = await _team("asha", "ravi", "meena")
    await login(client, "asha@kjsindia.com")
    cid = (await _channel(client, member_ids=[ids["ravi"]]))["id"]

    await login(client, "meena@kjsindia.com")
    for r in (
        await client.get(f"{C}/channels/{cid}"),
        await client.patch(f"{C}/channels/{cid}", json={"name": "mine now"}, headers=HDR),
        await client.post(f"{C}/channels/{cid}/members", json={"user_ids": [ids["meena"]]}, headers=HDR),
        await client.delete(f"{C}/channels/{cid}/members/{ids['ravi']}", headers=HDR),
        await client.get(f"{C}/channels/99999"),  # doesn't exist: the same answer
    ):
        assert r.status_code == 404 and r.json()["code"] == "not_found"


async def test_dm_is_made_once_per_pair(client):
    ids = await _team("asha", "ravi")
    await login(client, "asha@kjsindia.com")
    first = (await client.post(f"{C}/dm/{ids['ravi']}", headers=HDR)).json()
    again = (await client.post(f"{C}/dm/{ids['ravi']}", headers=HDR)).json()
    assert first["id"] == again["id"] and first["kind"] == "dm" and first["title"] == "ravi"
    assert first["dm_user"] == {"id": ids["ravi"], "name": "ravi"} and first["member_count"] == 2

    await login(client, "ravi@kjsindia.com")
    theirs = (await client.post(f"{C}/dm/{ids['asha']}", headers=HDR)).json()
    assert theirs["id"] == first["id"] and theirs["title"] == "asha"

    r = await client.post(f"{C}/dm/{ids['ravi']}", headers=HDR)
    assert r.status_code == 422 and r.json()["code"] == "dm_self"
    assert (await client.post(f"{C}/dm/99999", headers=HDR)).status_code == 422


async def test_dm_two_clicks_at_once_still_one_dm():
    ids = await _team("asha", "ravi")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as a, \
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as b:
        await login(a, "asha@kjsindia.com")
        await login(b, "ravi@kjsindia.com")
        ra, rb = await asyncio.gather(a.post(f"{C}/dm/{ids['ravi']}", headers=HDR),
                                      b.post(f"{C}/dm/{ids['asha']}", headers=HDR))
    assert ra.status_code == rb.status_code == 200 and ra.json()["id"] == rb.json()["id"]
    async with AsyncSessionLocal() as db:
        assert len((await db.scalars(select(ChatChannel).where(ChatChannel.kind == "dm"))).all()) == 1


async def test_dm_cannot_be_renamed_or_changed(client):
    ids = await _team("asha", "ravi", "meena")
    await login(client, "asha@kjsindia.com")
    cid = (await client.post(f"{C}/dm/{ids['ravi']}", headers=HDR)).json()["id"]
    for r in (
        await client.patch(f"{C}/channels/{cid}", json={"name": "hi"}, headers=HDR),
        await client.post(f"{C}/channels/{cid}/members", json={"user_ids": [ids["meena"]]}, headers=HDR),
        await client.delete(f"{C}/channels/{cid}/members/{ids['asha']}", headers=HDR),
    ):
        assert r.status_code == 422 and r.json()["code"] == "not_for_dm"


async def test_archived_channel_is_read_only(client):
    ids = await _team("asha", "ravi", "meena")
    await login(client, "asha@kjsindia.com")
    cid = (await _channel(client, member_ids=[ids["ravi"]]))["id"]

    await login(client, "ravi@kjsindia.com")
    r = await client.patch(f"{C}/channels/{cid}", json={"archived": True}, headers=HDR)
    assert r.status_code == 403 and r.json()["code"] == "not_owner"

    await login(client, "asha@kjsindia.com")
    assert (await client.patch(f"{C}/channels/{cid}", json={"archived": True}, headers=HDR)).json()["archived"] is True
    for r in (
        await client.patch(f"{C}/channels/{cid}", json={"name": "new"}, headers=HDR),
        await client.post(f"{C}/channels/{cid}/members", json={"user_ids": [ids["meena"]]}, headers=HDR),
        await client.delete(f"{C}/channels/{cid}/members/{ids['ravi']}", headers=HDR),
    ):
        assert r.status_code == 409 and r.json()["code"] == "archived"
    assert (await client.get(f"{C}/channels/{cid}")).status_code == 200  # still readable

    r = await client.patch(f"{C}/channels/{cid}", json={"archived": False, "name": "sales-2"}, headers=HDR)
    assert r.json()["archived"] is False and r.json()["name"] == "sales-2"
    assert [a.after["archived"] for a in await _actions("chat.channel_archived")] == [True]
    assert len(await _actions("chat.channel_unarchived")) == 1


async def test_channel_owner_rules(client):
    ids = await _team("asha", "ravi", "meena")
    await login(client, "asha@kjsindia.com")
    cid = (await _channel(client, member_ids=[ids["ravi"]]))["id"]

    await login(client, "ravi@kjsindia.com")
    assert (await client.patch(f"{C}/channels/{cid}", json={"name": "x2"}, headers=HDR)).status_code == 403
    assert (await client.post(f"{C}/channels/{cid}/members", json={"user_ids": [ids["meena"]]},
                              headers=HDR)).status_code == 403
    assert (await client.delete(f"{C}/channels/{cid}/members/{ids['asha']}", headers=HDR)).status_code == 403

    await login(client, "asha@kjsindia.com")
    r = await client.post(f"{C}/channels/{cid}/members", json={"user_ids": [ids["meena"], ids["ravi"]]}, headers=HDR)
    assert [m["name"] for m in r.json()["members"]] == ["asha", "ravi", "meena"]  # ravi not added twice
    assert (await client.delete(f"{C}/channels/{cid}/members/{ids['meena']}", headers=HDR)).status_code == 204
    r = await client.delete(f"{C}/channels/{cid}/members/{ids['meena']}", headers=HDR)
    assert r.status_code == 404 and r.json()["code"] == "not_a_member"
    removed = await _actions("chat.member_removed")
    assert len(removed) == 1 and removed[0].before["user_id"] == ids["meena"]


async def test_group_any_member_adds_but_only_owner_removes(client):
    ids = await _team("asha", "ravi", "meena", "dev")
    await login(client, "asha@kjsindia.com")
    cid = (await _channel(client, kind="group", name="", member_ids=[ids["ravi"], ids["meena"]]))["id"]

    await login(client, "ravi@kjsindia.com")
    r = await client.post(f"{C}/channels/{cid}/members", json={"user_ids": [ids["dev"]]}, headers=HDR)
    assert r.status_code == 200 and r.json()["member_count"] == 4
    assert (await client.patch(f"{C}/channels/{cid}", json={"name": "Lunch"}, headers=HDR)).json()["title"] == "Lunch"
    assert (await client.delete(f"{C}/channels/{cid}/members/{ids['dev']}", headers=HDR)).status_code == 403


async def test_last_owner_leaving_hands_over_and_last_person_archives(client):
    ids = await _team("asha", "ravi", "meena")
    await login(client, "asha@kjsindia.com")
    cid = (await _channel(client, member_ids=[ids["ravi"], ids["meena"]]))["id"]
    assert (await client.delete(f"{C}/channels/{cid}/members/{ids['asha']}", headers=HDR)).status_code == 204
    assert (await client.get(f"{C}/channels/{cid}")).status_code == 404  # gone for me

    await login(client, "ravi@kjsindia.com")
    ch = (await client.get(f"{C}/channels/{cid}")).json()
    assert ch["my_role"] == "owner" and ch["member_count"] == 2  # ravi joined before meena
    assert len(await _actions("chat.member_left")) == 1

    await client.delete(f"{C}/channels/{cid}/members/{ids['ravi']}", headers=HDR)
    await login(client, "meena@kjsindia.com")
    await client.delete(f"{C}/channels/{cid}/members/{ids['meena']}", headers=HDR)
    async with AsyncSessionLocal() as db:
        assert (await db.get(ChatChannel, cid)).archived_at is not None
