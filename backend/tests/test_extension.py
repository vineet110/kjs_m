"""Browser extension (Phase C): connecting, device keys, site visits (checked-in time only, no double
counting, never_record, no ?query), hourly blocks and outcomes, idle through the extension, who sees what."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.core.config import ini
from app.core.database import AsyncSessionLocal
from app.models.attendance import Attendance, AttendancePunch
from app.models.extension import ExtensionDevice, SiteBlock, SiteVisit
from app.models.monitor import IdlePeriod
from app.models.notification import Notification
from app.models.user import User
from app.services import extension_service as ext
from tests.conftest import HDR, login, make_user


@pytest.fixture
def setting(monkeypatch):
    def set_(section, key, value):
        monkeypatch.setenv(f"KJS__{section.upper()}__{key.upper()}", str(value))
        ini.reload_now()
    yield set_
    monkeypatch.undo()
    ini.reload_now()


def iso(t: datetime) -> str:
    return t.isoformat()


async def _connect(client, email="ravi@kjsindia.com", check_in=True) -> tuple[str, int]:
    """Log in, check in, get a code and swap it for a key. Returns (key, user id)."""
    client.headers.update(HDR)
    await login(client, email)
    if check_in:
        assert (await client.post("/api/v1/attendance/check-in")).status_code == 200
        await _checked_in_earlier(minutes=60)
    code = (await client.post("/api/v1/monitor/extension/code")).json()["code"]
    r = await client.post("/api/v1/ext/connect", json={"code": code, "name": "Chrome on Windows"})
    assert r.status_code == 200, r.text
    async with AsyncSessionLocal() as db:
        uid = await db.scalar(select(User.id).where(User.email == email))
    return r.json()["key"], uid


async def _checked_in_earlier(minutes: int) -> None:
    """Move today's check-in back, so visits from the last few minutes fall inside checked-in time."""
    async with AsyncSessionLocal() as db:
        for p in (await db.scalars(select(AttendancePunch))).all():
            p.punched_at -= timedelta(minutes=minutes)
        for a in (await db.scalars(select(Attendance))).all():
            a.check_in_at -= timedelta(minutes=minutes)
        await db.commit()


def bearer(key: str) -> dict:
    return {"authorization": f"Bearer {key}"}


async def _visits(**where) -> list[SiteVisit]:
    async with AsyncSessionLocal() as db:
        q = select(SiteVisit).order_by(SiteVisit.started_at)
        for k, v in where.items():
            q = q.where(getattr(SiteVisit, k) == v)
        return list((await db.scalars(q)).all())


# ---------- Connecting ----------
async def test_connect_once_and_key_works(client):
    await make_user("ravi@kjsindia.com")
    key, uid = await _connect(client)
    r = await client.get("/api/v1/ext/status", headers=bearer(key))
    assert r.status_code == 200 and r.json()["checked_in"] is True and r.json()["user_name"] == "ravi"
    assert r.json()["config"]["send_minutes"] == 5
    async with AsyncSessionLocal() as db:
        d = await db.scalar(select(ExtensionDevice))
    assert d.key_hash != key and len(d.key_hash) == 64  # only the hash is stored


async def test_code_works_once_and_expires(client, setting):
    await make_user("ravi@kjsindia.com")
    client.headers.update(HDR)
    await login(client, "ravi@kjsindia.com")
    code = (await client.post("/api/v1/monitor/extension/code")).json()["code"]
    assert (await client.post("/api/v1/ext/connect", json={"code": code})).status_code == 200
    assert (await client.post("/api/v1/ext/connect", json={"code": code})).json()["code"] == "bad_code"  # used
    code = (await client.post("/api/v1/monitor/extension/code")).json()["code"]
    newer = (await client.post("/api/v1/monitor/extension/code")).json()["code"]
    assert (await client.post("/api/v1/ext/connect", json={"code": code})).json()["code"] == "bad_code"  # replaced
    async with AsyncSessionLocal() as db:
        await ext.connect(db, newer, "x", now=datetime.now(timezone.utc))  # still fine now
    code = (await client.post("/api/v1/monitor/extension/code")).json()["code"]
    async with AsyncSessionLocal() as db:
        with pytest.raises(Exception):
            await ext.connect(db, code, "x", now=datetime.now(timezone.utc) + timedelta(minutes=11))  # expired


async def test_unknown_or_switched_off_key_is_refused(client):
    await make_user("admin@kjsindia.com", role="admin")
    await make_user("ravi@kjsindia.com")
    key, uid = await _connect(client)
    assert (await client.get("/api/v1/ext/status", headers=bearer("not-a-key"))).json()["code"] == "bad_device"
    assert (await client.get("/api/v1/ext/status")).json()["code"] == "bad_device"  # no key at all
    async with AsyncSessionLocal() as db:
        dev_id = await db.scalar(select(ExtensionDevice.id))
    await login(client, "admin@kjsindia.com")
    assert [d["id"] for d in (await client.get(f"/api/v1/work/{uid}/devices")).json()] == [dev_id]
    assert (await client.post(f"/api/v1/work/devices/{dev_id}/disable")).status_code == 200
    r = await client.get("/api/v1/ext/status", headers=bearer(key))
    assert r.status_code == 401 and r.json()["code"] == "bad_device"


async def test_employee_switches_off_only_own_device(client):
    await make_user("ravi@kjsindia.com")
    await make_user("priya@kjsindia.com")
    await _connect(client)
    async with AsyncSessionLocal() as db:
        dev_id = await db.scalar(select(ExtensionDevice.id))
    await login(client, "priya@kjsindia.com")
    assert (await client.post(f"/api/v1/monitor/extension/devices/{dev_id}/disable")).status_code == 404
    await login(client, "ravi@kjsindia.com")
    assert (await client.post(f"/api/v1/monitor/extension/devices/{dev_id}/disable")).status_code == 200


# ---------- Site visits ----------
async def test_visits_saved_without_query_and_never_record_dropped(client):
    await make_user("ravi@kjsindia.com")
    key, _ = await _connect(client)
    now = datetime.now(timezone.utc)
    visits = [
        {"id": "a1", "url": "https://www.indiamart.com/search?q=twill&token=SECRET#top", "title": "Twill",
         "started_at": iso(now - timedelta(seconds=90)), "ended_at": iso(now - timedelta(seconds=30))},
        {"id": "a2", "url": "https://netbanking.hdfcbank.com/login?otp=123456", "title": "Bank",
         "started_at": iso(now - timedelta(seconds=60)), "ended_at": iso(now - timedelta(seconds=10))},
        {"id": "a3", "url": "chrome://settings", "title": "Settings",
         "started_at": iso(now - timedelta(seconds=60)), "ended_at": iso(now - timedelta(seconds=10))},
    ]
    r = await client.post("/api/v1/ext/sites", json={"visits": visits}, headers=bearer(key))
    assert r.json() == {"saved": 1, "skipped": 2}
    [v] = await _visits()
    assert (v.domain, v.url) == ("indiamart.com", "https://www.indiamart.com/search")
    assert "SECRET" not in v.url and v.seconds == 60


async def test_same_batch_twice_is_counted_once(client):
    await make_user("ravi@kjsindia.com")
    key, _ = await _connect(client)
    now = datetime.now(timezone.utc)
    batch = {"visits": [{"id": "b1", "url": "https://mail.google.com/mail/u/0/", "title": "Inbox",
                         "started_at": iso(now - timedelta(seconds=120)), "ended_at": iso(now - timedelta(seconds=20))}]}
    assert (await client.post("/api/v1/ext/sites", json=batch, headers=bearer(key))).json()["saved"] == 1
    assert (await client.post("/api/v1/ext/sites", json=batch, headers=bearer(key))).json()["saved"] == 0
    assert len(await _visits()) == 1
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(func.sum(SiteBlock.seconds))) == 100  # blocks not doubled either


async def test_data_while_checked_out_is_refused_and_cut_to_checked_in_time(client):
    await make_user("ravi@kjsindia.com")
    key, _ = await _connect(client, check_in=False)
    now = datetime.now(timezone.utc)
    visit = {"id": "c1", "url": "https://youtube.com/watch", "title": "Video",
             "started_at": iso(now - timedelta(seconds=60)), "ended_at": iso(now - timedelta(seconds=5))}
    r = await client.post("/api/v1/ext/sites", json={"visits": [visit]}, headers=bearer(key))
    assert r.json() == {"saved": 0, "skipped": 1}  # checked out: nothing kept
    # Check in now: a visit that began before check-in keeps only the checked-in part
    await client.post("/api/v1/attendance/check-in")
    later = datetime.now(timezone.utc) + timedelta(seconds=30)
    visit = {"id": "c2", "url": "https://youtube.com/watch", "title": "Video",
             "started_at": iso(now - timedelta(minutes=10)), "ended_at": iso(later)}
    async with AsyncSessionLocal() as db:
        d, u = await ext.device_for_key(db, key)
        r = await ext.save_visits(db, d, u, [{**visit, "started_at": now - timedelta(minutes=10), "ended_at": later}],
                                  now=later)
    [v] = await _visits()
    assert r["saved"] == 1 and v.seconds <= 31 and v.started_at >= now - timedelta(seconds=1)


async def test_idle_through_the_extension(client):
    await make_user("ravi@kjsindia.com")
    key, _ = await _connect(client)
    started = datetime.now(timezone.utc) - timedelta(minutes=20)
    assert (await client.post("/api/v1/ext/idle", json={"state": "started", "at": iso(started)},
                              headers=bearer(key))).status_code == 200
    st = (await client.get("/api/v1/monitor/state")).json()
    assert st["idle"]["minutes"] == 20 and st["extension"] == "connected"
    await client.post("/api/v1/ext/idle", json={"state": "ended", "at": iso(datetime.now(timezone.utc))},
                      headers=bearer(key))
    async with AsyncSessionLocal() as db:
        assert (await db.scalar(select(IdlePeriod))).ended_at is not None


# ---------- Sites tab and outcomes ----------
async def _seed_block(uid: int, minutes: int, hours_ago: int = 2) -> int:
    async with AsyncSessionLocal() as db:
        hour = ext._hour_start(datetime.now(timezone.utc) - timedelta(hours=hours_ago))
        b = SiteBlock(user_id=uid, domain="indiamart.com", hour_start=hour, seconds=minutes * 60)
        db.add(b)
        await db.commit()
        return b.id


async def test_outcome_asked_for_long_blocks_written_by_owner_only(client):
    await make_user("admin@kjsindia.com", role="admin")
    await make_user("ravi@kjsindia.com")
    await make_user("priya@kjsindia.com")
    _, uid = await _connect(client)
    long_id = await _seed_block(uid, 22)
    await _seed_block(uid, 3, hours_ago=3)  # under outcome_min_minutes: not asked
    sites = (await client.get("/api/v1/work/me/sites")).json()
    assert [b["id"] for b in sites["blocks"]] == [long_id]
    await login(client, "priya@kjsindia.com")
    r = await client.post(f"/api/v1/monitor/sites/blocks/{long_id}/outcome", json={"outcome": "mine"})
    assert r.status_code == 404  # not her block
    await login(client, "ravi@kjsindia.com")
    r = await client.post(f"/api/v1/monitor/sites/blocks/{long_id}/outcome", json={"outcome": "Found 3 buyers"})
    assert r.status_code == 200
    await login(client, "admin@kjsindia.com")
    blocks = (await client.get(f"/api/v1/work/{uid}/sites")).json()["blocks"]
    assert blocks[0]["outcome"] == "Found 3 buyers"


async def test_employee_cannot_see_another_employees_sites(client):
    await make_user("ravi@kjsindia.com")
    await make_user("priya@kjsindia.com")
    _, uid = await _connect(client)
    await login(client, "priya@kjsindia.com")
    assert (await client.get(f"/api/v1/work/{uid}/sites")).status_code == 403
    assert (await client.get("/api/v1/work/me/sites")).json()["blocks"] == []  # her own: empty


async def test_reminder_once_and_old_visits_deleted(client, setting):
    await make_user("ravi@kjsindia.com")
    _, uid = await _connect(client)
    await _seed_block(uid, 12)
    async with AsyncSessionLocal() as db:
        assert (await ext.extension_watch(db))["reminded"] == 1
        await db.commit()
        assert (await ext.extension_watch(db))["reminded"] == 0
        await db.commit()
        n = await db.scalar(select(Notification).where(Notification.kind == "monitor.site_outcome"))
        assert n.user_id == uid and n.email_status == "skipped"
        out = await ext.extension_watch(db, now=datetime.now(timezone.utc) + timedelta(days=91))
        await db.commit()
    assert out["blocks_deleted"] == 1


def test_clean_url_rules(setting):
    assert ext.clean_url("https://user:pass@Example.com:8443/a/b?x=1#y") == ("example.com", "https://example.com:8443/a/b")
    assert ext.clean_url("ftp://x.com/") == ("", "")
    setting("monitoring", "store_query", "true")
    assert ext.clean_url("https://x.com/p?q=1#f")[1] == "https://x.com/p?q=1#f"
    assert ext.never_recorded("netbanking.hdfcbank.com") and not ext.never_recorded("nothdfcbank.com")


async def test_area_off_refuses_extension(client, setting):
    await make_user("ravi@kjsindia.com")
    key, _ = await _connect(client)
    setting("modules", "monitoring", "off")
    assert (await client.get("/api/v1/ext/status", headers=bearer(key))).json()["code"] == "module_off"
    assert (await client.post("/api/v1/ext/connect", json={"code": "KJS-AAAA-BBBB"})).json()["code"] == "module_off"
