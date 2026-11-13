"""Fixes from the 27 Oct production-readiness review. Each test is one problem that must stay fixed."""
import time
from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import select, update

from app.core import rate_limit
from app.core.config import production_problems
from app.core.config.ini import LoggingIni
from app.core.database import AsyncSessionLocal
from app.jobs import runner
from app.models.lead import Lead
from app.models.task import Task
from app.models.user import User
from app.services import attendance_service, auth_service, notification_service
from app.services import board_service as boards
from tests.conftest import HDR, id_token, login, make_user
from tests.test_boards import _ids, board_body


async def _id(email: str) -> int:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(User.id).where(User.email == email))


# ---------- Attendance ----------
async def test_approving_a_missed_check_in_keeps_the_real_check_out(client):
    # Before: an empty check-out in the request wiped the real one, so the day had 0 hours.
    await make_user("e@kjsindia.com")
    await make_user("m@kjsindia.com", permissions=["attendance.manage"])
    async with AsyncSessionLocal() as db:
        u = await db.scalar(select(User).where(User.email == "e@kjsindia.com"))
        row = await attendance_service.check_in(db, u, now=attendance_service.to_utc(date(2026, 10, 20), "11:00"))
        await attendance_service.check_out(db, u, now=attendance_service.to_utc(date(2026, 10, 20), "18:05"))
    await login(client, "e@kjsindia.com")
    r = await client.post("/api/v1/attendance/regularizations", headers=HDR,
                          json={"day": "2026-10-20", "check_in": "09:30", "reason": "Forgot to punch in"})
    assert r.status_code == 201, r.text
    await login(client, "m@kjsindia.com")
    assert (await client.post(f"/api/v1/attendance/approvals/{r.json()['id']}", json={"approve": True},
                              headers=HDR)).json()["status"] == "approved"
    async with AsyncSessionLocal() as db:
        row = await db.get(type(row), row.id)
        assert attendance_service.hm(row.check_in_at) == "09:30"
        assert attendance_service.hm(row.check_out_at) == "18:05"


async def test_check_out_does_not_close_a_day_old_forgotten_shift():
    # Before: checked in Monday, forgot to check out, pressed "check out" Tuesday evening = 33 hours.
    await make_user("e@kjsindia.com")
    async with AsyncSessionLocal() as db:
        u = await db.scalar(select(User).where(User.email == "e@kjsindia.com"))
        await attendance_service.check_in(db, u, now=attendance_service.to_utc(date(2026, 10, 26), "09:00"))
        with pytest.raises(Exception) as e:
            await attendance_service.check_out(db, u, now=attendance_service.to_utc(date(2026, 10, 27), "18:30"))
        assert getattr(e.value, "code", "") == "not_checked_in"
        # a real night shift (under 16 h) still closes yesterday's row
        await attendance_service.check_in(db, u, now=attendance_service.to_utc(date(2026, 10, 28), "20:00"))
        row = await attendance_service.check_out(db, u, now=attendance_service.to_utc(date(2026, 10, 29), "02:00"))
        assert row.day == date(2026, 10, 28)


# ---------- Accounts and login ----------
async def test_approver_cannot_turn_a_disabled_account_back_on(client):
    await make_user("hr@kjsindia.com", permissions=["leads.view", "staff.approve"])
    await make_user("old@kjsindia.com", status="disabled", permissions=["leads.view", "catalog.edit"])
    await login(client, "hr@kjsindia.com")
    r = await client.post(f"/api/v1/admin/users/{await _id('old@kjsindia.com')}/status", json={"status": "active"},
                          headers=HDR)
    assert r.status_code == 403


async def test_a_stranger_cannot_lock_someone_else_out():
    # Before: 10 wrong passwords from anywhere locked the email, even for its real owner.
    await make_user("boss@kjsindia.com")
    async with AsyncSessionLocal() as db:
        for _ in range(10):
            with pytest.raises(Exception):
                await auth_service.login(db, "boss@kjsindia.com", "wrong-guess-1", ip_hash="attacker")
        with pytest.raises(Exception) as e:
            await auth_service.login(db, "boss@kjsindia.com", "password1234", ip_hash="attacker")
        assert e.value.status_code == 429  # the guessing network is locked
        user, _ = await auth_service.login(db, "boss@kjsindia.com", "password1234", ip_hash="office")
        assert user.email == "boss@kjsindia.com"  # the real owner still gets in


def test_rate_limiter_forgets_idle_keys():
    lim = rate_limit.RateLimiter(limit=lambda: 5, window_seconds=1)
    for i in range(100):
        lim.hit(f"random-{i}@example.com")
    for q in lim._hits.values():  # make every hit old
        q[0] -= 10
    lim._swept_at -= rate_limit.SWEEP_EVERY_SECONDS + 1
    lim.hit("one-more")
    assert list(lim._hits) == ["one-more"]
    rate_limit.ALL.remove(lim)


async def test_long_name_and_email_do_not_break_actions(client):
    # Before: name + email over 117 characters made every audited action fail with a 500.
    email = ("x" * 60) + "@" + ("k" * 60) + ".com"
    await make_user(email)
    async with AsyncSessionLocal() as db:
        await db.execute(update(User).where(User.email == email).values(name="N" * 100))
        await db.commit()
    await login(client, email)
    assert (await client.post("/api/v1/attendance/check-in", headers=HDR)).status_code == 200


# ---------- Background jobs and config ----------
def test_a_typo_in_the_log_level_is_refused():
    with pytest.raises(ValidationError):
        LoggingIni(level="verbose")
    with pytest.raises(ValidationError):
        LoggingIni(levels={"app.services": "loud"})


async def test_readiness_fails_when_jobs_stop(client):
    try:
        runner.last_tick = time.monotonic()
        assert (await client.get("/api/health/ready")).status_code == 200
        runner.last_tick = time.monotonic() - 10 ** 6  # last round a long time ago
        r = await client.get("/api/health/ready")
        assert r.status_code == 503 and r.json()["code"] == "jobs_stalled"
    finally:
        runner.last_tick = None


def test_production_refuses_unsafe_cors():
    from tests.test_production_checks import make
    assert production_problems(make(ALLOWED_ORIGINS="https://www.kjsindia.com")) == []
    for bad in ("*", "http://www.kjsindia.com", "https://www.kjsindia.com,*"):
        assert len(production_problems(make(ALLOWED_ORIGINS=bad))) == 1, bad


async def test_mail_server_down_costs_one_try_not_fifty(client, monkeypatch):
    await make_user("boss@kjsindia.com", permissions=["leads.view", "leads.view_all"])
    for i in range(3):
        assert (await client.post("/api/v1/public/leads", headers=HDR, json={
            "name": f"Buyer {i}", "email": f"b{i}@example.com", "consent": True, "phone": "+91 98765 43210"})).status_code == 201
    tries = []

    def down():
        tries.append(1)
        raise OSError("connection refused")

    monkeypatch.setattr(notification_service.settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(notification_service, "_smtp_connect", down)
    from app.models.notification import Notification
    for _ in range(5):  # CR10: an outage of 5 runs used to use up the oldest emails' attempts, then lose them
        result = await runner.run_job("send_emails")
        assert result["failed"] == 0
    assert len(tries) == 5  # one try per run, not one per email
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(select(Notification.email_status, Notification.email_attempts))).all()
    assert {s for s, _ in rows} == {"pending"} and {a for _, a in rows} == {0}  # all wait, none lost

    sent = []

    class Server:
        def send_message(self, msg):
            sent.append(msg["To"])

        def quit(self):
            pass

    monkeypatch.setattr(notification_service, "_smtp_connect", lambda: Server())
    await runner.run_job("send_emails")  # the server is back: every email goes out
    async with AsyncSessionLocal() as db:
        assert set((await db.scalars(select(Notification.email_status))).all()) == {"sent"}
    assert sent


# ---------- Batches and imports ----------
async def test_import_refuses_more_rows_than_allowed(client, monkeypatch):
    from app.services import assign_service
    monkeypatch.setattr(assign_service, "MAX_ROWS", 3)
    await make_user("boss@kjsindia.com", permissions=["leads.view", "assign.manage"])
    await login(client, "boss@kjsindia.com")
    csv = "Company,Category\n" + "".join(f"Firm {i},coffee\n" for i in range(4))
    r = await client.post("/api/v1/assign/import", files={"file": ("big.csv", csv.encode(), "text/csv")}, headers=HDR)
    assert r.status_code == 422 and r.json()["code"] == "too_many_rows"


async def test_reimporting_a_list_skips_known_buyers(client):
    await make_user("boss@kjsindia.com", permissions=["leads.view", "assign.manage"])
    await login(client, "boss@kjsindia.com")
    csv = b"Company,Email,Category\nAl Noor,omar@alnoor.ae,coffee\nLagos Foods,,coffee\n"
    first = (await client.post("/api/v1/assign/import", files={"file": ("a.csv", csv, "text/csv")}, headers=HDR)).json()
    again = (await client.post("/api/v1/assign/import", files={"file": ("a.csv", csv, "text/csv")}, headers=HDR)).json()
    assert first["added"] == 2 and again["added"] == 0
    assert {s["reason"] for s in again["skipped"]} == {"already imported"}


async def test_finished_batch_cannot_be_reopened(client):
    from tests.test_assign import _import, _uid
    from app.services import assign_service
    await make_user("boss@kjsindia.com", permissions=["leads.view", "assign.manage"])
    await login(client, "boss@kjsindia.com")
    await _import(client)
    await make_user("a@kjsindia.com")
    a = await _uid("a@kjsindia.com")
    await client.post(f"/api/v1/assign/staff/{a}/categories", json={"categories": ["coffee"]}, headers=HDR)
    await login(client, "a@kjsindia.com")
    await client.post("/api/v1/attendance/check-in", headers=HDR)
    async with AsyncSessionLocal() as db:
        await assign_service.run(db, None, datetime.now(timezone.utc))
    recs = (await client.get("/api/v1/assign/my-batches")).json()[0]["records"]
    for rec in recs:
        await client.patch(f"/api/v1/assign/records/{rec['id']}", json={"status": "done", "outcome": "ok"}, headers=HDR)
    r = await client.patch(f"/api/v1/assign/records/{recs[0]['id']}", json={"status": "assigned", "outcome": ""},
                           headers=HDR)
    assert r.status_code == 409 and r.json()["code"] == "batch_closed"


# ---------- Leads ----------
async def test_lead_status_rules_keep_the_timers_right(client):
    await make_user("e@kjsindia.com")
    assert (await client.post("/api/v1/public/leads", headers=HDR, json={
        "name": "Omar", "email": "omar@alnoor.ae", "consent": True, "phone": "+91 98765 43210"})).status_code == 201
    await login(client, "e@kjsindia.com")
    async with AsyncSessionLocal() as db:
        lead_id = await db.scalar(select(Lead.id))

    async def to(status, outcome=""):
        return await client.patch(f"/api/v1/employee/leads/{lead_id}", json={"status": status, "outcome": outcome},
                                  headers=HDR)

    assert (await to("closed", "Won")).status_code == 204
    assert (await to("closed", "Won")).status_code == 409  # closing twice would reset the dates
    assert (await to("new")).status_code == 409  # answered leads can't go back to "new"
    assert (await to("contacted")).status_code == 204  # reopen
    async with AsyncSessionLocal() as db:
        lead = await db.get(Lead, lead_id)
        assert lead.resolved_at is None and lead.responded_at is not None


# ---------- Order boards ----------
async def test_board_finishes_once_and_closes_its_tasks(client):
    await make_user("boss@kjsindia.com", permissions=["leads.view", "boards.manage"])
    await make_user("pack@kjsindia.com")
    _, pack = await _ids("boss@kjsindia.com", "pack@kjsindia.com")
    await login(client, "boss@kjsindia.com")
    assert (await client.post("/api/v1/boards", json=board_body(pack, pack), headers=HDR)).status_code == 201
    r = await client.post("/api/v1/boards/ABC117-3/finish", json={"final_status": "Cancelled"}, headers=HDR)
    assert r.status_code == 200
    again = await client.post("/api/v1/boards/ABC117-3/finish", json={"final_status": "Delivered"}, headers=HDR)
    assert again.status_code == 409
    async with AsyncSessionLocal() as db:
        statuses = (await db.scalars(select(Task.status).where(Task.source == "board"))).all()
    assert statuses and set(statuses) == {"done"}


async def test_board_dates_and_sizes_are_bounded(client):
    await make_user("boss@kjsindia.com", permissions=["leads.view", "boards.manage"])
    await login(client, "boss@kjsindia.com")
    for body in ({"start": "0001-01-01", "deadline": "9998-12-31", "sizes": [50, 50]},
                 {"start": "2026-10-26", "deadline": "2026-11-07", "sizes": [10 ** 9]},
                 {"start": "2026-11-07", "deadline": "2026-10-26", "sizes": [100]}):
        assert (await client.post("/api/v1/boards/preview", json=body, headers=HDR)).status_code == 422, body


async def test_board_files_match_the_code_whatever_the_case(client):
    await make_user("boss@kjsindia.com", permissions=["leads.view", "boards.manage"])
    await make_user("pack@kjsindia.com")
    _, pack = await _ids("boss@kjsindia.com", "pack@kjsindia.com")
    await login(client, "boss@kjsindia.com")
    await client.post("/api/v1/boards", json=board_body(pack, pack), headers=HDR)
    up = await client.post("/api/v1/files", data={"owner_type": "board", "owner_id": "abc117-3"},
                           files={"file": ("po.pdf", b"%PDF", "application/pdf")}, headers=HDR)
    assert up.status_code == 201 and up.json()["owner_id"] == "ABC117-3"
    listed = (await client.get("/api/v1/files?owner_type=board&owner_id=ABC117-3")).json()
    assert [f["id"] for f in listed] == [up.json()["id"]]


# ---------- Files ----------
async def test_product_files_need_a_real_product(client):
    await make_user("cat@kjsindia.com", permissions=["leads.view", "catalog.edit"])
    await login(client, "cat@kjsindia.com")
    r = await client.post("/api/v1/files", data={"owner_type": "product", "owner_id": "no-such-product"},
                          files={"file": ("a.pdf", b"%PDF", "application/pdf")}, headers=HDR)
    assert r.status_code == 403


async def test_public_photos_are_cacheable_staff_files_are_not(client):
    await make_user("cat@kjsindia.com", permissions=["leads.view", "catalog.edit"])
    await login(client, "cat@kjsindia.com")
    p = (await client.post("/api/v1/admin/products", json={"category_slug": "coffee", "name": "Stick Coffee"},
                           headers=HDR)).json()
    f = (await client.post("/api/v1/files", data={"owner_type": "product", "owner_id": p["slug"], "is_public": "true"},
                           files={"file": ("photo.png", b"\x89PNG..", "image/png")}, headers=HDR)).json()
    staff = await client.get(f"/api/v1/files/{f['id']}/download")
    assert staff.headers["cache-control"] == "private, no-store" and staff.content == b"\x89PNG.."
    client.cookies.clear()
    public = await client.get(f"/api/v1/public/files/{f['id']}")
    assert public.headers["cache-control"].startswith("public") and public.content == b"\x89PNG.."


async def test_deleted_files_are_purged_from_storage_later(client, monkeypatch):
    from app.core import storage as storage_mod
    from app.models.file import StoredFile
    await make_user("cat@kjsindia.com", permissions=["leads.view", "catalog.edit", "files.approve"])
    await make_user("boss@kjsindia.com", role="admin")
    await login(client, "cat@kjsindia.com")
    p = (await client.post("/api/v1/admin/products", json={"category_slug": "coffee", "name": "Stick Coffee"},
                           headers=HDR)).json()
    f = (await client.post("/api/v1/files", data={"owner_type": "product", "owner_id": p["slug"]},
                           files={"file": ("a.pdf", b"%PDF", "application/pdf")}, headers=HDR)).json()
    await client.post(f"/api/v1/files/{f['id']}/delete-request", json={"reason": "old version"}, headers=HDR)
    real_delete = storage_mod.LocalStorage.delete

    def broken(self, key):
        raise storage_mod.StorageError("disk busy")

    monkeypatch.setattr(storage_mod.LocalStorage, "delete", broken)
    await login(client, "boss@kjsindia.com")
    r = await client.post(f"/api/v1/files/{f['id']}/delete-decision", json={"approve": True}, headers=HDR)
    assert r.status_code == 200, r.text  # the decision is saved even though storage failed
    monkeypatch.setattr(storage_mod.LocalStorage, "delete", real_delete)
    assert (await runner.run_job("purge_deleted_files"))["purged"] == 1
    async with AsyncSessionLocal() as db:
        assert (await db.get(StoredFile, f["id"])).purged_at is not None


# ---------- Tasks ----------
async def test_task_dates_need_a_time_zone_and_fields_cant_be_nulled(client):
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    naive = await client.post("/api/v1/tasks", json={"title": "Call Omar", "due_at": "2026-10-27T10:00:00"}, headers=HDR)
    assert naive.status_code == 422
    t = (await client.post("/api/v1/tasks", json={"title": "Call Omar", "due_at": "2026-10-27T10:00:00Z"},
                           headers=HDR)).json()
    assert (await client.patch(f"/api/v1/tasks/{t['id']}", json={"title": None}, headers=HDR)).status_code == 422
    assert (await client.patch(f"/api/v1/tasks/{t['id']}", json={"due_at": None}, headers=HDR)).status_code == 200


async def test_one_pending_regularization_per_day_even_on_a_double_click():
    from app.models.attendance import Regularization
    from sqlalchemy.exc import IntegrityError
    await make_user("e@kjsindia.com")
    uid = await _id("e@kjsindia.com")
    at = datetime(2026, 10, 20, 4, 0, tzinfo=timezone.utc)
    async with AsyncSessionLocal() as db:
        db.add(Regularization(user_id=uid, day=date(2026, 10, 20), check_in_at=at, reason="a"))
        await db.commit()
        db.add(Regularization(user_id=uid, day=date(2026, 10, 20), check_in_at=at + timedelta(minutes=5), reason="b"))
        with pytest.raises(IntegrityError):
            await db.commit()


def test_rate_key_counts_an_ipv6_block_as_one_visitor():
    """CR6: a bot rotating through its own IPv6 /64 must not get a fresh limit per address."""
    from app.core.security import rate_key
    assert rate_key("2001:db8:1:2:aaaa::1") == rate_key("2001:db8:1:2:ffff:1:2:3") == "2001:db8:1:2::/64"
    assert rate_key("2001:db8:1:3::1") != rate_key("2001:db8:1:2::1")
    assert rate_key("::ffff:1.2.3.4") == "1.2.3.4" and rate_key("1.2.3.4") != rate_key("1.2.3.5")
    assert rate_key("testclient") == "testclient" and rate_key(None) is None and rate_key("") is None


async def test_the_office_is_not_blocked_by_its_own_logins_and_signups():
    """CR7: everyone in the office shares one address. Successful logins don't count, sign-ups allow 30."""
    await make_user("staff@kjsindia.com")
    async with AsyncSessionLocal() as db:
        for _ in range(40):
            await auth_service.login(db, id_token("staff@kjsindia.com"), ip_hash="office")
        for i in range(30):
            await auth_service.signup(db, id_token(f"new{i}@kjsindia.com"), f"New {i}", "+919876543210", ip_hash="office")
        with pytest.raises(Exception) as e:
            await auth_service.signup(db, id_token("new99@kjsindia.com"), "One more", "+919876543210", ip_hash="office")
        assert e.value.status_code == 429


async def test_strangers_on_many_networks_cannot_lock_out_the_office():
    """CR5: strangers must not lock the real person out. Bad tokens are counted per network only, so
    attackers on other networks (however many) never block the office."""
    from app.core.config.ini import cfg
    await make_user("boss@kjsindia.com")
    async with AsyncSessionLocal() as db:
        for n in range(10):
            for _ in range(cfg().app.login_failures_per_ip):
                with pytest.raises(Exception):
                    await auth_service.login(db, "fake-token-from-an-attacker", ip_hash=f"attacker-{n}")
        user, _ = await auth_service.login(db, id_token("boss@kjsindia.com"), ip_hash="office")
        assert user.email == "boss@kjsindia.com"  # the office still gets in
        with pytest.raises(Exception) as e:
            await auth_service.login(db, id_token("boss@kjsindia.com"), ip_hash="attacker-0")
        assert e.value.status_code == 429  # the attackers' own network stays blocked
