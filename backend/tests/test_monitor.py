"""Monitoring Phase B (app/services/monitor_service.py): screenshots, screen sharing on/off, breaks, idle,
the monitor_watch job, the backup skipping screenshots/, and who may see what."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app import backup_r2
from app.core.config import ini
from app.core.database import AsyncSessionLocal
from app.core.storage import storage
from app.models.attendance import Attendance
from app.models.monitor import Break, IdlePeriod, Screenshot, ShareEvent
from app.models.notification import Notification
from app.models.user import User
from app.services import attendance_service as att
from app.services import monitor_service as svc
from tests.conftest import HDR, login, make_user
from tests.test_backup_r2 import Bucket

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 2000


@pytest.fixture
def setting(monkeypatch):
    def set_(section, key, value):
        monkeypatch.setenv(f"KJS__{section.upper()}__{key.upper()}", str(value))
        ini.reload_now()
    yield set_
    monkeypatch.undo()
    ini.reload_now()


async def _user(email: str) -> User:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(User).where(User.email == email))


async def _setup(client, checked_in=True):
    await make_user("admin@kjsindia.com", role="admin")
    await make_user("ravi@kjsindia.com")
    client.headers.update(HDR)  # the portal's CSRF header on every POST
    await login(client, "ravi@kjsindia.com")
    if checked_in:
        assert (await client.post("/api/v1/attendance/check-in")).status_code == 200
    return await _user("ravi@kjsindia.com")


async def _shot(client, data=JPEG):
    return await client.post("/api/v1/monitor/screenshot", files={"file": ("s.jpg", data, "image/jpeg")})


async def _count(model, **where) -> int:
    async with AsyncSessionLocal() as db:
        q = select(func.count()).select_from(model)
        for k, v in where.items():
            q = q.where(getattr(model, k) == v)
        return await db.scalar(q)


async def _alerts(kind: str) -> list[str]:
    async with AsyncSessionLocal() as db:
        return list((await db.scalars(select(Notification.title).where(Notification.kind == kind))).all())


# ---------- Screenshots ----------
async def test_screenshot_saved_while_checked_in(client):
    ravi = await _setup(client)
    r = await _shot(client)
    assert r.status_code == 200, r.text
    async with AsyncSessionLocal() as db:
        s = await db.scalar(select(Screenshot))
    assert s.user_id == ravi.id and s.storage_key.startswith(f"screenshots/{ravi.id}/")
    assert storage().get(s.storage_key) == JPEG


async def test_screenshot_refused_when_checked_out(client):
    await _setup(client, checked_in=False)
    r = await _shot(client)
    assert r.status_code == 409 and r.json()["code"] == "not_checked_in"
    await client.post("/api/v1/attendance/check-in")
    await client.post("/api/v1/attendance/check-out")
    assert (await _shot(client)).json()["code"] == "not_checked_in"
    assert await _count(Screenshot) == 0


async def test_screenshot_refused_on_break_bad_file_too_big_too_soon(client, setting):
    await _setup(client)
    assert (await _shot(client, b"GIF89a....")).json()["code"] == "bad_image"
    setting("monitoring", "max_screenshot_kb", 50)
    assert (await _shot(client, JPEG + b"0" * 60 * 1024)).json()["code"] == "too_big"
    assert (await _shot(client)).status_code == 200
    assert (await _shot(client)).json()["code"] == "too_soon"  # one per interval
    await client.post("/api/v1/monitor/break/start")
    assert (await _shot(client)).json()["code"] == "on_break"
    assert await _count(Screenshot) == 1


async def test_only_monitor_view_sees_screenshots(client):
    ravi = await _setup(client)
    await _shot(client)
    async with AsyncSessionLocal() as db:
        sid = await db.scalar(select(Screenshot.id))
    # the employee: not their own, not anyone's
    assert (await client.get(f"/api/v1/work/{ravi.id}/screenshots")).status_code == 403
    assert (await client.get(f"/api/v1/work/{ravi.id}/screenshots/{sid}/image")).status_code == 403
    await login(client, "admin@kjsindia.com")
    r = await client.get(f"/api/v1/work/{ravi.id}/screenshots")
    assert [s["id"] for s in r.json()["screenshots"]] == [sid]
    img = await client.get(f"/api/v1/work/{ravi.id}/screenshots/{sid}/image")
    assert img.status_code == 200 and img.content == JPEG and "private" in img.headers["cache-control"]
    # the id must belong to that person (no reading screenshots through another person's link)
    assert (await client.get(f"/api/v1/work/{ravi.id + 1}/screenshots/{sid}/image")).status_code == 404


async def test_screenshots_are_never_files(client):
    """They live in storage under screenshots/, with no stored_files row: /files can't serve them."""
    await _setup(client)
    await _shot(client)
    await login(client, "admin@kjsindia.com")
    r = await client.get("/api/v1/files", params={"owner_type": "screenshot", "owner_id": "1"})
    assert r.status_code in (400, 403, 404, 422) or r.json() == []


# ---------- Clean-up job ----------
async def test_old_screenshots_deleted_files_and_rows(client, setting):
    ravi = await _setup(client)
    await _shot(client)
    async with AsyncSessionLocal() as db:
        s = await db.scalar(select(Screenshot))
        key = s.storage_key
        s.taken_at = datetime.now(timezone.utc) - timedelta(days=31)
        await db.commit()
        out = await svc.monitor_watch(db)
        await db.commit()
    assert out["screenshots_deleted"] == 1 and await _count(Screenshot) == 0
    with pytest.raises(Exception):
        storage().get(key)
    assert ravi  # kept for readability


# ---------- Backup ----------
def test_backup_skips_screenshots():
    app = Bucket({"board/A/1-po.pdf": b"%PDF", "screenshots/7/2026-11-14/a.jpg": JPEG})
    bkp = Bucket()
    r = backup_r2.sync_files(app, bkp, datetime(2026, 11, 14).date(), 30)
    assert r["copied"] == 1 and list(bkp.objs) == ["files/board/A/1-po.pdf"]


# ---------- Screen sharing ----------
async def test_refused_alerts_admins_at_once(client):
    await _setup(client)
    assert (await client.post("/api/v1/monitor/share", json={"state": "refused"})).status_code == 200
    assert await _alerts("monitor.share_refused") == ["ravi refused screen sharing"]
    async with AsyncSessionLocal() as db:
        n = await db.scalar(select(Notification).where(Notification.kind == "monitor.share_refused"))
    assert n.email_status == "skipped"  # bell only, no email copy


async def test_stopped_alerts_only_after_gap_minutes_and_once(client):
    ravi = await _setup(client)
    await client.post("/api/v1/monitor/share", json={"state": "started"})
    await client.post("/api/v1/monitor/share", json={"state": "stopped"})
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        assert (await svc.monitor_watch(db, now=now + timedelta(minutes=2)))["gaps"] == 0  # under 5 minutes
        await db.commit()
        assert (await svc.monitor_watch(db, now=now + timedelta(minutes=6)))["gaps"] == 1
        await db.commit()
        assert (await svc.monitor_watch(db, now=now + timedelta(minutes=12)))["gaps"] == 0  # once
        await db.commit()
    assert len(await _alerts("monitor.share_gap")) == 1
    async with AsyncSessionLocal() as db:
        gaps = await svc.share_gaps(db, ravi.id, att.today_local())
    assert [(g["to"], g["state"]) for g in gaps] == [(None, "stopped")]  # still off


async def test_stopped_then_started_again_is_no_alert(client):
    await _setup(client)
    await client.post("/api/v1/monitor/share", json={"state": "stopped"})
    await client.post("/api/v1/monitor/share", json={"state": "started"})
    async with AsyncSessionLocal() as db:
        out = await svc.monitor_watch(db, now=datetime.now(timezone.utc) + timedelta(minutes=10))
        await db.commit()
    assert out["gaps"] == 0 and await _alerts("monitor.share_gap") == []


async def test_sharing_events_ignored_when_checked_out(client):
    await _setup(client, checked_in=False)
    await client.post("/api/v1/monitor/share", json={"state": "stopped"})
    assert await _count(ShareEvent) == 0


# ---------- Breaks ----------
async def test_break_start_end_and_limit_alert_once(client, setting):
    ravi = await _setup(client)
    setting("monitoring", "break_minutes_per_day", 30)
    r = await client.post("/api/v1/monitor/break/start")
    assert r.json()["on_break"] is True
    assert (await client.post("/api/v1/monitor/break/start")).json()["code"] == "already_on_break"
    async with AsyncSessionLocal() as db:  # pretend it began 40 minutes ago
        b = await db.scalar(select(Break))
        b.started_at -= timedelta(minutes=40)
        await db.commit()
    r = await client.post("/api/v1/monitor/break/end")
    assert r.json()["on_break"] is False and r.json()["break_minutes_today"] == 40
    assert await _alerts("monitor.break_limit") == ["ravi has taken 40 minutes of break today"]
    await client.post("/api/v1/monitor/break/start")
    await client.post("/api/v1/monitor/break/end")
    assert len(await _alerts("monitor.break_limit")) == 1  # once a day
    assert (await client.post("/api/v1/monitor/break/end")).json()["code"] == "not_on_break"
    assert ravi


async def test_break_needs_check_in_and_is_closed_by_check_out(client):
    await _setup(client, checked_in=False)
    assert (await client.post("/api/v1/monitor/break/start")).json()["code"] == "not_checked_in"
    await client.post("/api/v1/attendance/check-in")
    await client.post("/api/v1/monitor/break/start")
    await client.post("/api/v1/attendance/check-out")
    async with AsyncSessionLocal() as db:
        assert (await svc.monitor_watch(db))["breaks_closed"] == 1
        await db.commit()
    assert await _count(Break, ended_at=None) == 0


# ---------- Idle (the extension sends it in Phase C; tested through the service here) ----------
async def test_idle_shorter_than_warn_never_counts(client):
    ravi = await _setup(client)
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        u = await db.get(User, ravi.id)
        await svc.idle_started(db, u, now - timedelta(minutes=10))
        assert (await svc.state(db, u))["idle"] is None  # 10 < 15: no warning
        await svc.idle_ended(db, u, now)
    assert await _count(IdlePeriod) == 0  # removed, not kept as a tiny idle period


async def test_idle_warning_reason_and_admin_alert_once(client):
    ravi = await _setup(client)
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        u = await db.get(User, ravi.id)
        await svc.idle_started(db, u, now - timedelta(minutes=16))
    st = (await client.get("/api/v1/monitor/state")).json()
    assert st["idle"]["minutes"] == 16 and st["extension"] == "not_connected"
    idle_id = st["idle"]["id"]
    assert (await client.post(f"/api/v1/monitor/idle/{idle_id}/reason", json={"reason": "other"})).json()["code"] == "note_needed"
    assert (await client.post(f"/api/v1/monitor/idle/{idle_id}/reason", json={"reason": "call"})).status_code == 200
    async with AsyncSessionLocal() as db:
        assert (await svc.monitor_watch(db, now=now))["idle_warned"] == 1
        await db.commit()
        assert (await svc.monitor_watch(db, now=now + timedelta(minutes=15)))["idle_alerted"] == 1
        await db.commit()
        assert (await svc.monitor_watch(db, now=now + timedelta(minutes=20)))["idle_alerted"] == 0
        await db.commit()
    titles = await _alerts("monitor.idle")
    assert len(titles) == 1 and titles[0].startswith("ravi has been idle for 31 minutes")


async def test_idle_reason_only_for_own_period(client):
    ravi = await _setup(client)
    await make_user("priya@kjsindia.com")
    async with AsyncSessionLocal() as db:
        u = await db.get(User, ravi.id)
        await svc.idle_started(db, u, datetime.now(timezone.utc) - timedelta(minutes=20))
        idle_id = await db.scalar(select(IdlePeriod.id))
    await login(client, "priya@kjsindia.com")
    assert (await client.post(f"/api/v1/monitor/idle/{idle_id}/reason", json={"reason": "call"})).status_code == 404


async def test_idle_ignored_when_checked_out_or_on_break(client):
    ravi = await _setup(client)
    await client.post("/api/v1/monitor/break/start")
    async with AsyncSessionLocal() as db:
        u = await db.get(User, ravi.id)
        await svc.idle_started(db, u, datetime.now(timezone.utc) - timedelta(minutes=20))
    assert await _count(IdlePeriod) == 0


# ---------- Device, work pages, area switch ----------
async def test_phone_check_in_is_recorded_and_told(client):
    ravi = await _setup(client)
    assert (await client.post("/api/v1/monitor/device", json={"device": "phone"})).status_code == 200
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(Attendance.device).where(Attendance.user_id == ravi.id)) == "phone"
    assert await _alerts("monitor.phone") == ["ravi checked in from a phone"]


async def test_team_work_shows_break_sharing_device(client):
    ravi = await _setup(client)
    await client.post("/api/v1/monitor/device", json={"device": "laptop"})
    await client.post("/api/v1/monitor/share", json={"state": "started"})
    await client.post("/api/v1/monitor/break/start")
    await login(client, "admin@kjsindia.com")
    r = (await client.get("/api/v1/work/team")).json()
    row = next(x for x in r["rows"] if x["user_id"] == ravi.id)
    assert (row["on_break"], row["sharing"], row["device"], row["extension"]) == (True, "started", "laptop", "not_connected")
    assert r["summary"]["on_break"] == 1
    tl = (await client.get(f"/api/v1/work/{ravi.id}/timeline", params={"kinds": "break,screen"})).json()["items"]
    assert {i["kind"] for i in tl} == {"break", "screen"}


async def test_area_off_hides_monitor_routes(client, setting):
    await _setup(client)
    setting("modules", "monitoring", "off")
    assert (await client.get("/api/v1/monitor/state")).json()["code"] == "module_off"
    assert (await _shot(client)).json()["code"] == "module_off"
