from sqlalchemy import text

from app.core.database import engine
from tests.conftest import HDR, login, make_user


async def test_signup_then_pending_cannot_login(client):
    r = await client.post("/api/v1/auth/signup", headers=HDR,
                          json={"name": "Priya", "email": "Priya@KJSindia.com", "password": "password1234"})
    assert r.status_code == 201
    r = await client.post("/api/v1/auth/login", headers=HDR,
                          json={"email": "priya@kjsindia.com", "password": "password1234"})
    assert r.status_code == 403
    assert r.json()["code"] == "pending_approval"


async def test_duplicate_email_rejected(client):
    body = {"name": "A B", "email": "a@kjsindia.com", "password": "password1234"}
    assert (await client.post("/api/v1/auth/signup", json=body, headers=HDR)).status_code == 201
    r = await client.post("/api/v1/auth/signup", json=body, headers=HDR)
    assert r.status_code == 409 and r.json()["code"] == "email_taken"


async def test_wrong_password_same_message_as_unknown_user(client):
    await make_user("e@kjsindia.com")
    wrong = await client.post("/api/v1/auth/login", headers=HDR, json={"email": "e@kjsindia.com", "password": "nope-nope-nope"})
    unknown = await client.post("/api/v1/auth/login", headers=HDR, json={"email": "x@kjsindia.com", "password": "nope-nope-nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["message"] == unknown.json()["message"]


async def test_admin_approves_with_permissions_and_it_is_audited(client):
    await make_user("admin@kjsindia.com", role="admin")
    await client.post("/api/v1/auth/signup", headers=HDR,
                      json={"name": "Priya", "email": "priya@kjsindia.com", "password": "password1234"})
    await login(client, "admin@kjsindia.com")
    pending = (await client.get("/api/v1/admin/users?status=pending")).json()
    r = await client.post(f"/api/v1/admin/users/{pending[0]['id']}/approve", headers=HDR,
                          json={"permissions": ["leads.view_all"]})
    assert r.status_code == 200
    assert r.json()["status"] == "active"
    assert set(r.json()["permissions"]) == {"leads.view", "leads.view_all"}

    async with engine.connect() as conn:
        actions = (await conn.execute(text("SELECT action FROM audit_log ORDER BY id"))).scalars().all()
    assert "user.approved" in actions


async def test_unknown_permission_rejected(client):
    await make_user("admin@kjsindia.com", role="admin")
    await make_user("p@kjsindia.com", status="pending")
    await login(client, "admin@kjsindia.com")
    r = await client.post("/api/v1/admin/users/2/approve", headers=HDR, json={"permissions": ["god.mode"]})
    assert r.status_code == 422


async def test_me_and_logout(client):
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.json()["role"] == "employee"
    assert (await client.post("/api/v1/auth/logout", headers=HDR)).status_code == 204
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_disabled_user_is_logged_out(client):
    await make_user("admin@kjsindia.com", role="admin")
    await make_user("e@kjsindia.com")
    await login(client, "admin@kjsindia.com")
    r = await client.post("/api/v1/admin/users/2/status", headers=HDR, json={"status": "disabled"})
    assert r.status_code == 200
    r = await client.post("/api/v1/auth/login", headers=HDR, json={"email": "e@kjsindia.com", "password": "password1234"})
    assert r.status_code == 403 and r.json()["code"] == "disabled"


async def test_audit_log_cannot_be_deleted():
    async with engine.begin() as conn:
        await conn.execute(text("INSERT INTO audit_log (actor_label, action, entity_type) VALUES ('t', 't', 't')"))
    try:
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM audit_log"))
        raise AssertionError("delete should have been blocked")
    except Exception as e:  # asyncpg RaiseError wrapped by SQLAlchemy
        assert "append-only" in str(e)
