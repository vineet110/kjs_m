"""R55 edge cases: who gets a batch under each batches setting (config/modules.ini)."""
from app.core.config import ini
from tests.conftest import HDR, login, make_user
from tests.test_assign import _import, _uid


async def _plan(client, monkeypatch, level: str) -> tuple[list[int], int, int]:
    monkeypatch.setenv("KJS__MODULES__BATCHES", level)
    ini.reload_now()
    await make_user("root@kjsindia.com", role="admin")
    await login(client, "root@kjsindia.com")
    await _import(client)
    await make_user("a@kjsindia.com")
    await make_user("root2@kjsindia.com", role="admin")  # an admin with no categories: still no batch
    a, root = await _uid("a@kjsindia.com"), await _uid("root@kjsindia.com")
    for uid in (a, root):
        await client.post(f"/api/v1/assign/staff/{uid}/categories", json={"categories": ["coffee"]}, headers=HDR)
    for who in ("a@kjsindia.com", "root@kjsindia.com", "root2@kjsindia.com"):
        await login(client, who)
        await client.post("/api/v1/attendance/check-in", headers=HDR)
    await login(client, "root@kjsindia.com")
    r = await client.get("/api/v1/assign/preview")
    return ([p["user_id"] for p in r.json()] if r.status_code == 200 else [r.status_code]), a, root


async def test_with_batches_on_everyone_with_categories_gets_one(client, monkeypatch):
    plan, a, root = await _plan(client, monkeypatch, "on")
    assert sorted(plan) == sorted([a, root])


async def test_with_batches_admin_an_admin_without_categories_gets_none(client, monkeypatch):
    plan, a, root = await _plan(client, monkeypatch, "admin")
    assert plan == [root]
