"""app/reset_staff.py: every employee retired (never an admin), so the same emails can sign up fresh."""
from datetime import datetime, timezone

from sqlalchemy import select

from app import reset_staff
from app.core.database import AsyncSessionLocal
from app.core.errors import AppError
from app.models.audit import AuditLog
from app.models.lead import Lead
from app.models.user import User, UserSession
from tests.conftest import HDR, id_token, login, make_user, uid_of

SIGNUP = "/api/v1/auth/signup"


async def _users() -> dict[int, User]:
    async with AsyncSessionLocal() as db:
        return {u.id: u for u in (await db.scalars(select(User))).all()}


async def _setup(client) -> tuple[int, int]:
    await make_user("admin@kjsindia.com", role="admin")
    await make_user("e1@kjsindia.com")
    await make_user("e2@kjsindia.com", status="pending")
    await login(client, "e1@kjsindia.com")  # a session and activity-log lines, like a real test account
    async with AsyncSessionLocal() as db:
        e1 = await db.scalar(select(User.id).where(User.email == "e1@kjsindia.com"))
        admin = await db.scalar(select(User.id).where(User.email == "admin@kjsindia.com"))
        db.add(Lead(source="enquiry_form", name="Buyer", phone="+91 98765 43210", consent=True,
                    consent_at=datetime.now(timezone.utc), status="new", assigned_to=e1))
        await db.commit()
    return admin, e1


async def test_check_mode_changes_nothing(client, fake_firebase):
    await _setup(client)
    before = {i: (u.email, u.status, u.firebase_uid) for i, u in (await _users()).items()}
    r = await reset_staff.run(apply=False, keep=set(), out=lambda *_: None)
    assert sorted(r["retire"]) == ["e1@kjsindia.com", "e2@kjsindia.com"]  # the admin is never listed
    assert {i: (u.email, u.status, u.firebase_uid) for i, u in (await _users()).items()} == before
    assert fake_firebase.deleted == []


async def test_apply_retires_employees_and_the_same_email_signs_up_fresh(client, fake_firebase):
    admin, e1 = await _setup(client)
    r = await reset_staff.run(apply=True, keep=set(), out=lambda *_: None)
    assert r["failed"] == []
    users = await _users()
    assert (users[admin].email, users[admin].status) == ("admin@kjsindia.com", "active")  # untouched
    gone = users[e1]
    assert (gone.email, gone.status, gone.firebase_uid) == (f"removed-{e1}@invalid", "disabled", None)
    assert set(fake_firebase.deleted) == {uid_of("e1@kjsindia.com"), uid_of("e2@kjsindia.com")}
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(UserSession).where(UserSession.user_id == e1)) is None  # logged out
        assert await db.scalar(select(Lead.assigned_to)) is None  # their open lead is back to unassigned
        audit = (await db.scalars(select(AuditLog).where(AuditLog.action == "user.retired"))).all()
    assert len(audit) == 2 and {a.before["email"] for a in audit} == {"e1@kjsindia.com", "e2@kjsindia.com"}

    # The same email signs up as a new person, waiting for approval
    body = {"id_token": id_token("e1@kjsindia.com"), "name": "E One", "phone": "+91 98765 43210"}
    assert (await client.post(SIGNUP, json=body, headers=HDR)).status_code == 201
    fresh = [u for u in (await _users()).values() if u.email == "e1@kjsindia.com"]
    assert len(fresh) == 1 and fresh[0].id != e1 and fresh[0].status == "pending"

    # Running it again: the retired rows are skipped, only the fresh sign-up would go
    again = await reset_staff.run(apply=False, keep=set(), out=lambda *_: None)
    assert again["retire"] == ["e1@kjsindia.com"]


async def test_keep_protects_named_employees(client, fake_firebase):
    await _setup(client)
    r = await reset_staff.run(apply=True, keep={" E2@kjsindia.com "}, out=lambda *_: None)
    assert r["kept"] == ["e2@kjsindia.com"] and r["retire"] == ["e1@kjsindia.com"]
    emails = {u.email for u in (await _users()).values()}
    assert "e2@kjsindia.com" in emails and "e1@kjsindia.com" not in emails
    assert fake_firebase.deleted == [uid_of("e1@kjsindia.com")]


async def test_firebase_failure_leaves_the_person_as_they_were(client, fake_firebase, monkeypatch):
    _, e1 = await _setup(client)

    async def down(uid):
        raise AppError(503, "login_unavailable", "Google down")
    monkeypatch.setattr(reset_staff.firebase, "delete_user", down)
    r = await reset_staff.run(apply=True, keep=set(), out=lambda *_: None)
    assert sorted(r["failed"]) == ["e1@kjsindia.com", "e2@kjsindia.com"]
    users = await _users()
    assert (users[e1].email, users[e1].status) == ("e1@kjsindia.com", "active")  # run it again later
