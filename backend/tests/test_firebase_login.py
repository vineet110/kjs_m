"""Login through Firebase: verified emails only, accounts from before Firebase are linked safely, admin-made
accounts get a Firebase account, and disabling reaches Firebase. Firebase itself is faked (conftest.py)."""
import asyncio
import time
from types import SimpleNamespace

import pytest
from firebase_admin import auth as fb_auth
from firebase_admin import exceptions as firebase_errors
from sqlalchemy import select, text

from app.core import firebase
from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.models.user import User
from app.services import auth_service
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


# ---------- Review of #77: fixes ----------
# The real token check (firebase.verify_token / firebase.app), kept before conftest swaps in the fake
REAL_VERIFY, REAL_APP = firebase.verify_token, firebase.app
REAL_UID_BY_EMAIL, REAL_CREATE_USER = firebase.uid_by_email, firebase.create_user
ME = "/api/v1/auth/me"


def _raises(error: Exception):
    def fail(*args, **kwargs):
        raise error
    return fail


async def _admin_logged_in(client):
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")


async def test_approving_a_disabled_account_switches_firebase_back_on(client, fake_firebase):
    await _admin_logged_in(client)
    await make_user("e@kjsindia.com")
    uid = (await _user("e@kjsindia.com")).id
    await client.post(f"/api/v1/admin/users/{uid}/status", json={"status": "disabled"}, headers=HDR)
    assert fake_firebase.disabled[uid_of("e@kjsindia.com")] is True
    r = await client.post(f"/api/v1/admin/users/{uid}/approve", json={"permissions": []}, headers=HDR)
    assert r.status_code == 200
    assert fake_firebase.disabled[uid_of("e@kjsindia.com")] is False  # Firebase lets them sign in again


@pytest.mark.parametrize("step, error, status", [
    ("verify", fb_auth.InvalidIdTokenError("forged"), 401),
    ("verify", fb_auth.CertificateFetchError("Google's keys didn't load", None), 503),
    ("get_user", fb_auth.UserNotFoundError("account deleted in Firebase"), 401),
    ("get_user", firebase_errors.UnavailableError("Google is down"), 503),
])
async def test_firebase_errors_are_401_or_503_never_500(client, monkeypatch, step, error, status):
    await make_user("e@kjsindia.com")
    monkeypatch.setattr(firebase, "verify_token", REAL_VERIFY)
    monkeypatch.setattr(firebase, "app", lambda: object())
    good = {"uid": uid_of("e@kjsindia.com"), "email": "e@kjsindia.com", "email_verified": True, "iat": int(time.time())}
    monkeypatch.setattr(firebase.fb_auth, "verify_id_token", _raises(error) if step == "verify" else lambda t, app, **kw: good)
    monkeypatch.setattr(firebase.fb_auth, "get_user", _raises(error) if step == "get_user" else
                        lambda uid, app: SimpleNamespace(disabled=False, tokens_valid_after_timestamp=0))
    r = await client.post(LOGIN, json={"id_token": "a-real-looking-firebase-token"}, headers=HDR)
    assert r.status_code == status, r.text


@pytest.mark.parametrize("disabled, valid_after_s", [(True, 0), (False, 60)])
async def test_disabled_or_revoked_firebase_account_is_refused(client, monkeypatch, disabled, valid_after_s):
    await make_user("e@kjsindia.com")
    now = int(time.time())
    monkeypatch.setattr(firebase, "verify_token", REAL_VERIFY)
    monkeypatch.setattr(firebase, "app", lambda: object())
    monkeypatch.setattr(firebase.fb_auth, "verify_id_token", lambda t, app, **kw: {
        "uid": uid_of("e@kjsindia.com"), "email": "e@kjsindia.com", "email_verified": True, "iat": now})
    # valid_after 60 s after the token was made = the password changed since: the token is revoked
    monkeypatch.setattr(firebase.fb_auth, "get_user", lambda uid, app: SimpleNamespace(
        disabled=disabled, tokens_valid_after_timestamp=(now + valid_after_s) * 1000 if valid_after_s else 0))
    r = await client.post(LOGIN, json={"id_token": "a-real-looking-firebase-token"}, headers=HDR)
    assert r.status_code == 401


@pytest.mark.parametrize("key", ["{this is not json", '{"type": "not a service account"}'])
async def test_broken_key_is_a_setup_error_and_never_locks_the_office_out(client, monkeypatch, key):
    from app.core.config.ini import cfg
    monkeypatch.setattr(firebase, "verify_token", REAL_VERIFY)
    monkeypatch.setattr(firebase, "app", REAL_APP)
    monkeypatch.setattr(settings, "FIREBASE_SERVICE_ACCOUNT", key)
    for _ in range(cfg().app.login_failures_per_ip + 1):  # more than the bad-token limit: still no 429
        r = await client.post(LOGIN, json={"id_token": id_token("e@kjsindia.com")}, headers=HDR)
        assert r.status_code == 503 and r.json()["code"] == "login_not_set_up"


NEHA = {"name": "Neha", "email": "neha@kjsindia.com", "phone": "+91 98765 43210", "role": "employee",
        "employee_code": "KJS-020", "branch": "Mumbai"}


async def test_create_employee_reuses_a_half_finished_firebase_account(client, fake_firebase):
    fake_firebase.created[uid_of("neha@kjsindia.com")] = "neha@kjsindia.com"  # a sign-up that stopped halfway
    await _admin_logged_in(client)
    r = await client.post("/api/v1/admin/users", json=NEHA, headers=HDR)
    assert r.status_code == 201, r.text
    assert fake_firebase.reset == {uid_of("neha@kjsindia.com"): r.json()["temp_password"]}
    assert (await _user("neha@kjsindia.com")).firebase_uid == uid_of("neha@kjsindia.com")


async def test_create_employee_never_takes_over_another_accounts_login(client, fake_firebase):
    fake_firebase.created[uid_of("neha@kjsindia.com")] = "neha@kjsindia.com"
    async with AsyncSessionLocal() as db:  # that Firebase login already belongs to another row
        db.add(User(name="Other", email="other@kjsindia.com", firebase_uid=uid_of("neha@kjsindia.com"),
                    role="employee", status="active", permissions=["leads.view"]))
        await db.commit()
    await _admin_logged_in(client)
    r = await client.post("/api/v1/admin/users", json=NEHA, headers=HDR)
    assert r.status_code == 409
    assert fake_firebase.reset == {}  # nobody's password was changed


async def test_two_logins_at_once_both_find_the_linked_account(client):
    await make_user("old@kjsindia.com", linked=False)
    claims = await firebase.verify_token(id_token("old@kjsindia.com"))
    async with AsyncSessionLocal() as db:
        first = await auth_service._link_old_account(db, claims, None)
    async with AsyncSessionLocal() as db:  # the second click: the row is already linked
        second = await auth_service._link_old_account(db, claims, None)
    assert first.id == second.id


async def test_login_after_a_password_reset_ends_the_older_sessions(client, fake_firebase):
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    await make_user("e@kjsindia.com")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as old_laptop:
        await login(old_laptop, "e@kjsindia.com")
        await asyncio.sleep(0.01)
        fake_firebase.valid_after_ms[uid_of("e@kjsindia.com")] = int(time.time() * 1000)  # "Forgot password?" now
        await login(client, "e@kjsindia.com")  # the next login, with the new password
        assert (await old_laptop.get(ME)).status_code == 401
    assert (await client.get(ME)).status_code == 200


async def test_changing_your_own_password_keeps_this_browser_logged_in(client, fake_firebase):
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    fake_firebase.valid_after_ms[uid_of("e@kjsindia.com")] = int(time.time() * 1000)  # Firebase: changed now
    await asyncio.sleep(0.01)
    r = await client.post("/api/v1/auth/password", json={"id_token": id_token("e@kjsindia.com")}, headers=HDR)
    assert r.status_code == 204
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as phone:
        await login(phone, "e@kjsindia.com")  # a later login elsewhere
    assert (await client.get(ME)).status_code == 200  # this browser got a fresh session at the change


# ---------- Second review of #77 (14 Nov) ----------
async def test_token_check_allows_a_little_clock_difference(client, monkeypatch):
    await make_user("e@kjsindia.com")
    seen = {}
    monkeypatch.setattr(firebase, "verify_token", REAL_VERIFY)
    monkeypatch.setattr(firebase, "app", lambda: object())

    def verify(token, app, **kw):
        seen.update(kw)
        return {"uid": uid_of("e@kjsindia.com"), "email": "e@kjsindia.com", "email_verified": True, "iat": int(time.time())}
    monkeypatch.setattr(firebase.fb_auth, "verify_id_token", verify)
    monkeypatch.setattr(firebase.fb_auth, "get_user", lambda uid, app: SimpleNamespace(disabled=False, tokens_valid_after_timestamp=0))
    assert (await client.post(LOGIN, json={"id_token": "a-real-looking-firebase-token"}, headers=HDR)).status_code == 200
    assert seen["clock_skew_seconds"] == firebase.CLOCK_SKEW_SECONDS > 0


@pytest.mark.parametrize("error, status", [
    (firebase_errors.UnavailableError("Google is down"), 503),
    (ValueError("Google doesn't accept this email"), 422),
])
async def test_create_employee_when_google_fails_is_never_a_500(client, monkeypatch, error, status):
    await _admin_logged_in(client)
    monkeypatch.setattr(firebase, "uid_by_email", REAL_UID_BY_EMAIL)
    monkeypatch.setattr(firebase, "app", lambda: object())
    monkeypatch.setattr(firebase.fb_auth, "get_user_by_email", _raises(error))
    r = await client.post("/api/v1/admin/users", json=NEHA, headers=HDR)
    assert r.status_code == status, r.text
    assert await _user("neha@kjsindia.com") is None


async def test_create_employee_still_says_email_taken_from_firebase(client, monkeypatch):
    await _admin_logged_in(client)
    monkeypatch.setattr(firebase, "create_user", REAL_CREATE_USER)
    monkeypatch.setattr(firebase, "app", lambda: object())
    monkeypatch.setattr(firebase.fb_auth, "create_user", _raises(fb_auth.EmailAlreadyExistsError("taken", None, None)))
    r = await client.post("/api/v1/admin/users", json=NEHA, headers=HDR)
    assert r.status_code == 409 and r.json()["code"] == "email_taken"


async def test_signing_up_twice_with_the_same_login_is_fine(client):
    body = {"id_token": id_token("new@kjsindia.com"), "name": "New", "phone": "+91 98765 43210"}
    assert (await client.post(SIGNUP, json=body, headers=HDR)).status_code == 201
    assert (await client.post(SIGNUP, json=body, headers=HDR)).status_code == 201  # the retry, not a 409
    async with AsyncSessionLocal() as db:
        assert len((await db.scalars(select(User).where(User.email == "new@kjsindia.com"))).all()) == 1


async def test_signing_up_again_after_a_decision_is_still_refused(client):
    await make_user("e@kjsindia.com", status="rejected")
    r = await client.post(SIGNUP, json={"id_token": id_token("e@kjsindia.com"), "name": "E", "phone": "+91 98765 43210"},
                          headers=HDR)
    assert r.status_code == 409


async def test_approving_a_new_signup_makes_no_firebase_call(client, fake_firebase):
    await _admin_logged_in(client)
    await make_user("e@kjsindia.com", status="pending")
    uid = (await _user("e@kjsindia.com")).id
    r = await client.post(f"/api/v1/admin/users/{uid}/approve", json={"permissions": []}, headers=HDR)
    assert r.status_code == 200
    assert fake_firebase.disabled == {}
