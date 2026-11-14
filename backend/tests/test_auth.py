from sqlalchemy import text

from app.core.database import engine
from tests.conftest import HDR, id_token, login, make_user


def signup_body(email: str, name: str = "Priya") -> dict:
    return {"id_token": id_token(email), "name": name, "phone": "+91 98765 43210"}


async def test_signup_then_pending_cannot_login(client):
    r = await client.post("/api/v1/auth/signup", headers=HDR, json=signup_body("Priya@KJSindia.com"))
    assert r.status_code == 201
    r = await client.post("/api/v1/auth/login", headers=HDR, json={"id_token": id_token("priya@kjsindia.com")})
    assert r.status_code == 403
    assert r.json()["code"] == "pending_approval"


async def test_duplicate_email_rejected(client):
    # The email already belongs to another Firebase login (another person). The same person signing up
    # again is fine: test_signing_up_twice_with_the_same_login_is_fine (test_firebase_login.py).
    from app.core.database import AsyncSessionLocal
    from app.models.user import User
    async with AsyncSessionLocal() as db:
        db.add(User(name="A B", email="a@kjsindia.com", firebase_uid="uid-another-person", role="employee",
                    status="pending", permissions=["leads.view"]))
        await db.commit()
    r = await client.post("/api/v1/auth/signup", json=signup_body("a@kjsindia.com", "A B"), headers=HDR)
    assert r.status_code == 409 and r.json()["code"] == "email_taken"


async def test_fake_or_expired_token_is_refused(client):
    await make_user("e@kjsindia.com")
    r = await client.post("/api/v1/auth/login", headers=HDR, json={"id_token": "not-a-real-firebase-token-at-all"})
    assert r.status_code == 401 and r.json()["code"] == "bad_token"


async def test_admin_approves_with_permissions_and_it_is_audited(client):
    await make_user("admin@kjsindia.com", role="admin")
    await client.post("/api/v1/auth/signup", headers=HDR, json=signup_body("priya@kjsindia.com"))
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


async def test_disabled_user_is_logged_out(client, fake_firebase):
    await make_user("admin@kjsindia.com", role="admin")
    await make_user("e@kjsindia.com")
    await login(client, "admin@kjsindia.com")
    r = await client.post("/api/v1/admin/users/2/status", headers=HDR, json={"status": "disabled"})
    assert r.status_code == 200
    assert fake_firebase.disabled == {"uid-e@kjsindia.com": True}  # disabled in Firebase too
    r = await client.post("/api/v1/auth/login", headers=HDR, json={"id_token": id_token("e@kjsindia.com")})
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
