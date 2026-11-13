"""Login through Firebase: verified emails only, accounts from before Firebase are linked safely, admin-made
accounts get a Firebase account, and disabling reaches Firebase. Firebase itself is faked (conftest.py)."""
from sqlalchemy import select, text

from app.core.database import AsyncSessionLocal, engine
from app.models.user import User
from tests.conftest import HDR, id_token, login, make_user, uid_of

LOGIN = "/api/v1/auth/login"
SIGNUP = "/api/v1/auth/signup"


async def _user(email: str) -> User:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(User).where(User.email == email))


async def test_unverified_email_cannot_log_in(client):
    await make_user("e@kjsindia.com")
    r = await client.post(LOGIN, json={"id_token": id_token("e@kjsindia.com", verified=False)}, headers=HDR)
    assert r.status_code == 403 and r.json()["code"] == "email_not_verified"


async def test_firebase_account_without_staff_account_is_told_to_sign_up(client):
    r = await client.post(LOGIN, json={"id_token": id_token("stranger@example.com")}, headers=HDR)
    assert r.status_code == 403 and r.json()["code"] == "no_account"


async def test_signup_takes_the_email_from_the_token_not_the_form(client):
    body = {"id_token": id_token("real@kjsindia.com"), "name": "Real", "phone": "+91 98765 43210",
            "email": "boss@kjsindia.com"}  # an extra field is ignored
    assert (await client.post(SIGNUP, json=body, headers=HDR)).status_code == 201
    u = await _user("real@kjsindia.com")
    assert u.status == "pending" and u.firebase_uid == uid_of("real@kjsindia.com") and u.password_hash is None
    assert await _user("boss@kjsindia.com") is None


async def test_old_employee_account_is_linked_then_approved_again(client):
    await make_user("old@kjsindia.com", linked=False, permissions=["leads.view", "leads.view_all"])
    # Signing up again with the same email doesn't make a second account
    r = await client.post(SIGNUP, json={"id_token": id_token("old@kjsindia.com"), "name": "Old", "phone": "+91 98765 43210"},
                          headers=HDR)
    assert r.status_code == 201
    async with AsyncSessionLocal() as db:
        assert len((await db.scalars(select(User).where(User.email == "old@kjsindia.com"))).all()) == 1
    # Unverified: not linked (anyone can make a Firebase account with someone else's email)
    r = await client.post(LOGIN, json={"id_token": id_token("old@kjsindia.com", verified=False)}, headers=HDR)
    assert r.status_code == 403 and (await _user("old@kjsindia.com")).firebase_uid is None
    # Verified: linked, history kept, waits for approval again
    r = await client.post(LOGIN, json={"id_token": id_token("old@kjsindia.com")}, headers=HDR)
    assert r.status_code == 403 and r.json()["code"] == "pending_approval"
    u = await _user("old@kjsindia.com")
    assert u.firebase_uid == uid_of("old@kjsindia.com") and u.status == "pending"
    async with engine.connect() as conn:
        assert "user.linked_firebase" in (await conn.execute(text("SELECT action FROM audit_log"))).scalars().all()
    # An admin approves: now they get in
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    r = await client.post(f"/api/v1/admin/users/{u.id}/approve", json={"permissions": ["leads.view_all"]}, headers=HDR)
    assert r.status_code == 200
    await client.post("/api/v1/auth/logout", headers=HDR)
    await login(client, "old@kjsindia.com")


async def test_old_admin_account_stays_active_when_linked(client):
    # Nobody could approve the first admin, so an admin keeps working after linking
    async with AsyncSessionLocal() as db:
        db.add(User(name="Boss", email="boss@kjsindia.com", password_hash="old", firebase_uid=None,
                    role="admin", status="active", permissions=[]))
        await db.commit()
    await login(client, "boss@kjsindia.com")
    assert (await _user("boss@kjsindia.com")).status == "active"


async def test_signup_with_an_email_already_on_firebase_is_refused(client):
    await make_user("e@kjsindia.com")
    r = await client.post(SIGNUP, json={"id_token": id_token("e@kjsindia.com"), "name": "Copy", "phone": "+91 98765 43210"},
                          headers=HDR)
    assert r.status_code == 409


async def test_admin_made_account_gets_a_firebase_account(client, fake_firebase):
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    r = await client.post("/api/v1/admin/users", headers=HDR, json={
        "name": "Neha", "email": "neha@kjsindia.com", "phone": "+91 98765 43210", "role": "employee",
        "employee_code": "KJS-020", "branch": "Mumbai"})
    assert r.status_code == 201, r.text
    assert len(r.json()["temp_password"]) >= 10
    assert uid_of("neha@kjsindia.com") in fake_firebase.created
    u = await _user("neha@kjsindia.com")
    assert u.firebase_uid == uid_of("neha@kjsindia.com") and u.password_hash is None  # we never keep it
    await client.post("/api/v1/auth/logout", headers=HDR)
    await login(client, "neha@kjsindia.com")


async def test_turning_an_account_back_on_reaches_firebase(client, fake_firebase):
    await make_user("admin@kjsindia.com", role="admin")
    await make_user("e@kjsindia.com")
    await login(client, "admin@kjsindia.com")
    uid = (await _user("e@kjsindia.com")).id
    await client.post(f"/api/v1/admin/users/{uid}/status", json={"status": "disabled"}, headers=HDR)
    await client.post(f"/api/v1/admin/users/{uid}/status", json={"status": "active"}, headers=HDR)
    assert fake_firebase.disabled == {uid_of("e@kjsindia.com"): False}


async def test_password_changed_logs_out_other_browsers_only(client):
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    await make_user("e@kjsindia.com")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as phone:
        await login(phone, "e@kjsindia.com")  # another browser of the same person
        await login(client, "e@kjsindia.com")
        r = await client.post("/api/v1/auth/password", json={"id_token": id_token("e@kjsindia.com")}, headers=HDR)
        assert r.status_code == 204
        assert (await client.get("/api/v1/auth/me")).status_code == 200
        assert (await phone.get("/api/v1/auth/me")).status_code == 401
    async with engine.connect() as conn:
        assert "user.password_changed" in (await conn.execute(text("SELECT action FROM audit_log"))).scalars().all()
