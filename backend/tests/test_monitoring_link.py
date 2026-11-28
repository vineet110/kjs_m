"""The attendance feed for the laptop-monitoring server (INTEGRATION_PLAN.md Phase 1).

The rule that matters most: per person, events alternate punch_in -> punch_out with `at` going forward
(the monitoring server ignores a punch_in while a session is open and never edits history).
"""
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app.core.config import ini, settings
from app.core.database import AsyncSessionLocal
from app.models.monitoring_link import AttendanceEvent
from app.models.notification import Notification
from app.models.shift import Shift
from app.models.user import User
from app.services import attendance_service as att
from app.services import monitoring_link_service as svc
from tests.conftest import HDR, login, make_user

KEY = "k" * 40
BASE = "/api/v1/integrations/monitoring"


@pytest.fixture(autouse=True)
def feed_key(monkeypatch):
    monkeypatch.setattr(settings, "MONITORING_FEED_KEY", KEY)
    yield


def ist(d: str, hhmm: str) -> datetime:
    return att.to_utc(date.fromisoformat(d), hhmm)


async def _user(email="e@kjsindia.com", **fields) -> User:
    await make_user(email)
    async with AsyncSessionLocal() as db:
        u = await db.scalar(select(User).where(User.email == email))
        u.joined_on = date(2026, 10, 1)
        for k, v in fields.items():
            setattr(u, k, v)
        await db.commit()
        await db.refresh(u)
        return u


async def _punch(u: User, fn, d: str, hhmm: str):
    async with AsyncSessionLocal() as db:
        await fn(db, await db.merge(u), now=ist(d, hhmm))


async def _events(user_id: int) -> list[AttendanceEvent]:
    async with AsyncSessionLocal() as db:
        return list((await db.scalars(select(AttendanceEvent).where(AttendanceEvent.user_id == user_id)
                                      .order_by(AttendanceEvent.at, AttendanceEvent.id))).all())


def _alternates(events: list[AttendanceEvent]) -> bool:
    kinds = [e.event for e in events]
    times = [e.at for e in events]
    return (all(k == ("punch_in" if i % 2 == 0 else "punch_out") for i, k in enumerate(kinds))
            and times == sorted(times) and len(set(times)) == len(times))


async def _approve_fix(u: User, day: str, check_in: str, check_out: str | None):
    from app.models.attendance import Regularization
    async with AsyncSessionLocal() as db:
        if not await db.scalar(select(User.id).where(User.email == "boss@kjsindia.com")):
            await make_user("boss@kjsindia.com", permissions=["attendance.manage"])
        reg = Regularization(user_id=u.id, day=date.fromisoformat(day), check_in_at=ist(day, check_in),
                             check_out_at=ist(day, check_out) if check_out else None, reason="fix", status="pending")
        db.add(reg)
        await db.commit()
        boss = await db.scalar(select(User).where(User.email == "boss@kjsindia.com"))
        return await att.decide(db, boss, reg.id, True)


async def _auto_out(now: datetime) -> dict:
    async with AsyncSessionLocal() as db:
        return await svc.auto_out(db, now=now)


async def _night_shift() -> int:
    async with AsyncSessionLocal() as db:
        s = Shift(name="Night", code="N", start_time=time(21, 0), end_time=time(6, 0), is_night_shift=True)
        db.add(s)
        await db.commit()
        return s.id


# ---------- The key ----------
async def test_right_key_works(client):
    r = await client.get(f"{BASE}/api/employees", headers={"x-api-key": KEY})
    assert r.status_code == 200, r.text


@pytest.mark.parametrize("headers", [{}, {"x-api-key": "wrong"}, {"x-api-key": KEY + "x"}, {"x-api-key": ""}])
async def test_missing_or_wrong_key_is_refused(client, headers):
    r = await client.get(f"{BASE}/api/employees", headers=headers)
    assert r.status_code == 401 and r.json()["code"] == "bad_service_key"


async def test_key_in_the_address_is_not_enough(client):
    r = await client.get(f"{BASE}/api/employees", params={"x-api-key": KEY})
    assert r.status_code == 401


async def test_a_logged_in_admin_without_the_key_is_refused(client):
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    r = await client.get(f"{BASE}/api/employees", headers=HDR)
    assert r.status_code == 401


@pytest.mark.parametrize("configured", ["", "short-key"])
async def test_feed_is_closed_when_the_key_is_not_set_up(client, monkeypatch, configured):
    monkeypatch.setattr(settings, "MONITORING_FEED_KEY", configured)
    r = await client.get(f"{BASE}/api/employees", headers={"x-api-key": configured})
    assert r.status_code == 503 and r.json()["code"] == "feed_not_configured"


async def test_module_off_is_404_and_admin_level_still_runs(client, monkeypatch):
    monkeypatch.setenv("KJS__MODULES__MONITORING", "off")
    ini.reload_now()
    r = await client.get(f"{BASE}/api/employees", headers={"x-api-key": KEY})
    assert r.status_code == 404 and r.json()["code"] == "module_off"
    monkeypatch.setenv("KJS__MODULES__MONITORING", "admin")  # the pilot: the feed runs, pages admins-only
    ini.reload_now()
    r = await client.get(f"{BASE}/api/employees", headers={"x-api-key": KEY})
    assert r.status_code == 200


async def test_wrong_key_does_not_reveal_the_module_state(client, monkeypatch):
    monkeypatch.setenv("KJS__MODULES__MONITORING", "off")
    ini.reload_now()
    r = await client.get(f"{BASE}/api/employees", headers={"x-api-key": "wrong"})
    assert r.status_code == 401


def test_nginx_refuses_the_feed_from_outside():
    conf = (Path(__file__).resolve().parents[2] / "deploy" / "nginx" / "default.conf").read_text(encoding="utf-8")
    block = conf.index("location ^~ /api/v1/integrations/")
    assert "return 404;" in conf[block:block + 80]
    assert block < conf.index("location /api/ {")  # before the catch-all, so it wins


def test_module_needs_attendance():
    """The agent only runs while someone is checked in: monitoring can't be wider than attendance."""
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="monitoring = on needs attendance"):
        ini.ModulesIni(attendance="admin", batches="off", monitoring="on")
    assert ini.ModulesIni(attendance="admin", batches="off", monitoring="admin").monitoring == "admin"


# ---------- Employees ----------
async def test_employee_list_maps_the_fields_and_leaves_out_sign_ups(client):
    boss = await _user("boss2@kjsindia.com", branch="Sales")
    await _user("e@kjsindia.com", branch="Sales", reporting_to=boss.id)
    await _user("gone@kjsindia.com", status="disabled")
    await _user("new@kjsindia.com", status="pending")
    await _user("no@kjsindia.com", status="rejected")
    r = await client.get(f"{BASE}/api/employees", headers={"x-api-key": KEY})
    people = {p["email"]: p for p in r.json()["employees"]}
    assert set(people) == {"boss2@kjsindia.com", "e@kjsindia.com", "gone@kjsindia.com"}
    e = people["e@kjsindia.com"]
    assert e["manager_id"] == str(boss.id) and e["department"] == "Sales" and e["status"] == "active"
    assert e["employee_id"].isdigit() and e["backup_approver_id"] is None
    assert people["gone@kjsindia.com"]["status"] == "disabled"  # never "inactive": that revoked laptops for good
    assert people["boss2@kjsindia.com"]["manager_id"] is None


# ---------- Punches -> events ----------
async def test_check_in_and_out_write_events_the_feed_returns(client):
    u = await _user()
    since = datetime.now(timezone.utc) - timedelta(minutes=5)
    await _punch(u, att.check_in, "2026-10-26", "09:00")
    await _punch(u, att.check_out, "2026-10-26", "13:00")
    await _punch(u, att.check_in, "2026-10-26", "14:00")
    r = await client.get(f"{BASE}/api/attendance/changes", params={"since": since.isoformat()},
                         headers={"x-api-key": KEY})
    body = r.json()
    assert [c["event"] for c in body["changes"]] == ["punch_in", "punch_out", "punch_in"]
    assert all(c["employee_id"] == str(u.id) and c["at"].endswith("+00:00") for c in body["changes"])
    assert datetime.fromisoformat(body["changes"][0]["at"]) == ist("2026-10-26", "09:00")
    assert datetime.fromisoformat(body["server_time"]).tzinfo is not None


async def test_the_overlap_returns_recent_rows_again_and_misses_none(client):
    u = await _user()
    await _punch(u, att.check_in, "2026-10-26", "09:00")
    first = (await client.get(f"{BASE}/api/attendance/changes",
                              params={"since": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()},
                              headers={"x-api-key": KEY})).json()
    again = (await client.get(f"{BASE}/api/attendance/changes", params={"since": first["server_time"]},
                              headers={"x-api-key": KEY})).json()
    assert [c["id"] for c in again["changes"]] == [c["id"] for c in first["changes"]]  # repeats are fine


async def test_a_failed_punch_writes_no_event():
    u = await _user()
    await _punch(u, att.check_in, "2026-10-26", "09:00")
    with pytest.raises(Exception):
        await _punch(u, att.check_in, "2026-10-26", "09:05")  # already checked in
    assert [e.event for e in await _events(u.id)] == ["punch_in"]


async def test_a_forgotten_check_out_is_closed_before_the_next_check_in():
    u = await _user()
    await _punch(u, att.check_in, "2026-10-26", "09:00")  # never checked out
    await _punch(u, att.check_in, "2026-10-27", "09:10")
    ev = await _events(u.id)
    assert [e.event for e in ev] == ["punch_in", "punch_out", "punch_in"] and _alternates(ev)
    assert ev[1].source == "auto" and ev[1].at == ist("2026-10-26", "19:30")  # the auto-out time, not +16 h


# ---------- Auto-out ----------
async def test_auto_out_at_shift_end_plus_grace_and_tells_the_person():
    u = await _user()
    await _punch(u, att.check_in, "2026-10-26", "09:00")
    assert (await _auto_out(ist("2026-10-26", "19:29")))["closed"] == 0  # 18:30 + 60 min not reached
    assert (await _auto_out(ist("2026-10-26", "19:31")))["closed"] == 1
    assert (await _auto_out(ist("2026-10-26", "19:40")))["closed"] == 0  # once
    ev = await _events(u.id)
    assert ev[-1].event == "punch_out" and ev[-1].at == ist("2026-10-26", "19:30") and ev[-1].source == "auto"
    async with AsyncSessionLocal() as db:
        n = await db.scalar(select(Notification).where(Notification.user_id == u.id))
    assert n.kind == "monitoring.auto_out" and "19:30" in n.title
    # The real check-out later sends nothing more (already closed here); the next day starts cleanly
    await _punch(u, att.check_out, "2026-10-26", "20:15")
    await _punch(u, att.check_in, "2026-10-27", "09:00")
    assert _alternates(await _events(u.id))


async def test_auto_out_skips_people_who_checked_out():
    u = await _user()
    await _punch(u, att.check_in, "2026-10-26", "09:00")
    await _punch(u, att.check_out, "2026-10-26", "18:00")
    assert (await _auto_out(ist("2026-10-27", "08:00")))["closed"] == 0


async def test_auto_out_follows_a_night_shift():
    u = await _user(shift_id=await _night_shift())
    await _punch(u, att.check_in, "2026-10-26", "21:00")
    assert (await _auto_out(ist("2026-10-27", "06:30")))["closed"] == 0  # ends 06:00 + 60 min
    assert (await _auto_out(ist("2026-10-27", "07:01")))["closed"] == 1


async def test_a_night_shift_checked_into_after_midnight_ends_that_morning():
    """Review finding: the 00:30 check-in used its own date, so the shift 'ended' a day later (16 h cap)."""
    u = await _user(shift_id=await _night_shift())
    await _punch(u, att.check_in, "2026-10-27", "00:30")  # the shift that began on the 26th
    assert (await _auto_out(ist("2026-10-27", "06:30")))["closed"] == 0
    assert (await _auto_out(ist("2026-10-27", "07:01")))["closed"] == 1
    assert (await _events(u.id))[-1].at == ist("2026-10-27", "07:00")


async def test_a_fix_closes_a_night_shift_checked_into_after_midnight():
    u = await _user(shift_id=await _night_shift())
    await _punch(u, att.check_in, "2026-10-27", "00:30")
    async with AsyncSessionLocal() as db:  # a fix of "the shift of the 26th": reg.day is the shift's start day
        await svc.on_regularization(db, u.id, date(2026, 10, 26), ist("2026-10-27", "05:00"), 999)
        await db.commit()
    ev = await _events(u.id)
    assert [e.source for e in ev] == ["punch", "regularization"] and ev[-1].at == ist("2026-10-27", "05:00")


async def test_overtime_after_shift_end_is_not_cut_after_an_hour():
    """Review finding: a check-in after shift end was closed at check-in + grace (60 min, or 1 s with grace 0)."""
    u = await _user()
    await _punch(u, att.check_in, "2026-10-26", "19:00")  # after the 18:30 shift end
    assert (await _auto_out(ist("2026-10-26", "22:59")))["closed"] == 0
    assert (await _auto_out(ist("2026-10-26", "23:01")))["closed"] == 1  # 19:00 + 4 h


def test_grace_can_not_be_zero(monkeypatch):
    monkeypatch.setenv("KJS__MONITORING_LINK__AUTO_OUT_GRACE_MINUTES", "0")
    ini.reload_now()
    assert ini.cfg().monitoring_link.auto_out_grace_minutes == 60  # refused: the last good value stays


def test_auto_out_never_after_max_shift_hours(monkeypatch):
    monkeypatch.setenv("KJS__MONITORING_LINK__AUTO_OUT_GRACE_MINUTES", "480")
    ini.reload_now()
    last_in = ist("2026-10-26", "09:00")
    # 18:30 + 8 h = 02:30 next day, but the 16-hour cap after a 09:00 check-in is 01:00
    assert svc.auto_out_at(last_in, None) == ist("2026-10-27", "01:00")


# ---------- Regularizations ----------
async def test_a_fix_that_closes_an_open_day_sends_the_check_out():
    u = await _user()
    await _punch(u, att.check_in, "2026-10-26", "09:00")
    await _approve_fix(u, "2026-10-26", "09:00", "18:00")
    ev = await _events(u.id)
    assert [e.event for e in ev] == ["punch_in", "punch_out"] and ev[1].source == "regularization"
    assert ev[1].at == ist("2026-10-26", "18:00") and ev[1].ref.startswith("reg:")


async def test_a_fix_that_moves_times_already_sent_sends_nothing():
    u = await _user()
    await _punch(u, att.check_in, "2026-10-26", "09:30")
    await _punch(u, att.check_out, "2026-10-26", "18:00")
    await _approve_fix(u, "2026-10-26", "09:00", "18:30")  # earlier in, later out
    ev = await _events(u.id)
    assert [e.source for e in ev] == ["punch", "punch"]


async def test_a_fix_for_a_day_with_no_punches_sends_nothing():
    """It would open a session in the past on the monitoring side: tracked while off duty."""
    u = await _user()
    await _approve_fix(u, "2026-10-26", "09:00", None)
    await _approve_fix(u, "2026-10-27", "09:00", "18:00")
    assert await _events(u.id) == []


async def test_a_fix_after_auto_out_sends_nothing_more():
    u = await _user()
    await _punch(u, att.check_in, "2026-10-26", "09:00")
    await _auto_out(ist("2026-10-26", "20:00"))
    await _approve_fix(u, "2026-10-26", "09:00", "18:00")
    ev = await _events(u.id)
    assert [e.source for e in ev] == ["punch", "auto"] and _alternates(ev)


async def test_everything_mixed_still_alternates():
    u = await _user()
    steps = [(att.check_in, "2026-10-26", "09:00"), (att.check_out, "2026-10-26", "13:00"),
             (att.check_in, "2026-10-26", "14:00"),  # forgets to check out
             (att.check_in, "2026-10-27", "09:00"), (att.check_out, "2026-10-27", "18:00"),
             (att.check_in, "2026-10-28", "09:00")]
    for fn, d, t in steps:
        await _punch(u, fn, d, t)
    await _auto_out(ist("2026-10-28", "20:00"))
    await _approve_fix(u, "2026-10-28", "08:45", "18:10")
    await _punch(u, att.check_in, "2026-10-29", "09:00")
    assert _alternates(await _events(u.id))


# ---------- One person's events (the lock check) ----------
async def test_events_for_one_person_in_a_range(client):
    u = await _user()
    other = await _user("o@kjsindia.com")
    await _punch(u, att.check_in, "2026-10-24", "09:00")  # Saturday
    await _punch(u, att.check_out, "2026-10-24", "18:00")
    await _punch(other, att.check_in, "2026-10-24", "09:00")
    r = await client.get(f"{BASE}/api/attendance/events", headers={"x-api-key": KEY}, params={
        "employee_id": str(u.id), "from": ist("2026-10-21", "18:00").isoformat(),
        "to": ist("2026-10-26", "09:00").isoformat()})  # 4.6 days: v1's 3-day cap would have refused it
    assert r.status_code == 200
    assert [c["event"] for c in r.json()["changes"]] == ["punch_in", "punch_out"]


@pytest.mark.parametrize("params", [
    {"employee_id": "1", "from": "2026-10-02T00:00:00+00:00", "to": "2026-10-01T00:00:00+00:00"},  # backwards
    {"employee_id": "1", "from": "2026-10-01T00:00:00", "to": "2026-10-02T00:00:00"},  # no offset
    {"employee_id": "abc", "from": "2026-10-01T00:00:00+00:00", "to": "2026-10-02T00:00:00+00:00"},
    {"employee_id": "\u00b2", "from": "2026-10-01T00:00:00+00:00", "to": "2026-10-02T00:00:00+00:00"},  # "²"
    {"employee_id": "99999999999", "from": "2026-10-01T00:00:00+00:00", "to": "2026-10-02T00:00:00+00:00"},
])
async def test_bad_event_queries_are_422(client, params):
    r = await client.get(f"{BASE}/api/attendance/events", headers={"x-api-key": KEY}, params=params)
    assert r.status_code == 422


async def test_a_range_over_31_days_is_shortened_not_refused(client):
    """Review finding: after a 35-day leave the lock check got 422, which monitoring reads as 'CRM down'."""
    u = await _user()
    await _punch(u, att.check_in, "2026-10-26", "09:00")
    r = await client.get(f"{BASE}/api/attendance/events", headers={"x-api-key": KEY}, params={
        "employee_id": str(u.id), "from": ist("2026-09-20", "09:00").isoformat(),
        "to": ist("2026-10-27", "09:00").isoformat()})  # 37 days
    assert r.status_code == 200 and [c["event"] for c in r.json()["changes"]] == ["punch_in"]


async def test_changes_needs_an_offset(client):
    r = await client.get(f"{BASE}/api/attendance/changes", headers={"x-api-key": KEY},
                         params={"since": "2026-10-01T00:00:00"})
    assert r.status_code == 422


# ---------- Paging ----------
async def test_a_big_backlog_pages_forward_even_when_one_write_is_bigger_than_a_page(client, monkeypatch):
    monkeypatch.setenv("KJS__MONITORING_LINK__FEED_MAX_ROWS", "100")
    ini.reload_now()
    u = await _user()
    t1 = datetime.now(timezone.utc) - timedelta(hours=2)
    t2 = t1 + timedelta(minutes=30)
    async with AsyncSessionLocal() as db:
        for i in range(120):  # one transaction: one created_at for all 120
            db.add(AttendanceEvent(user_id=u.id, event="punch_in" if i % 2 == 0 else "punch_out",
                                   at=t1 + timedelta(seconds=i), source="backfill", created_at=t1))
        for i in range(30):
            db.add(AttendanceEvent(user_id=u.id, event="punch_in" if i % 2 == 0 else "punch_out",
                                   at=t2 + timedelta(seconds=i), source="backfill", created_at=t2))
        await db.commit()
    seen: set[str] = set()
    since = (t1 - timedelta(hours=1)).isoformat()
    for _ in range(3):
        body = (await client.get(f"{BASE}/api/attendance/changes", params={"since": since},
                                 headers={"x-api-key": KEY})).json()
        seen |= {c["id"] for c in body["changes"]}
        since = body["server_time"]
    assert len(seen) == 150


# ---------- Clean-up ----------
async def test_old_events_are_deleted():
    u = await _user()
    async with AsyncSessionLocal() as db:
        db.add(AttendanceEvent(user_id=u.id, event="punch_in", at=ist("2026-01-05", "09:00"), source="punch",
                               created_at=datetime.now(timezone.utc) - timedelta(days=100)))
        db.add(AttendanceEvent(user_id=u.id, event="punch_out", at=ist("2026-01-05", "18:00"), source="punch",
                               created_at=datetime.now(timezone.utc) - timedelta(days=100)))
        await db.commit()
    async with AsyncSessionLocal() as db:
        assert (await svc.purge_events(db))["purged"] == 2


def test_purge_runs_while_monitoring_is_off(monkeypatch):
    """Punches write events while the area is off, so the clean-up must run then too."""
    from app.jobs.runner import should_run
    monkeypatch.setenv("KJS__MODULES__MONITORING", "off")
    ini.reload_now()
    assert should_run("monitoring_events_purge", working=False)
    assert not should_run("monitoring_auto_out", working=True)


async def test_a_recent_backlog_keeps_the_overlap_and_server_time_is_never_in_the_future(client, monkeypatch):
    monkeypatch.setenv("KJS__MONITORING_LINK__FEED_MAX_ROWS", "100")
    ini.reload_now()
    u = await _user()
    t = datetime.now(timezone.utc) - timedelta(seconds=5)
    async with AsyncSessionLocal() as db:
        for i in range(101):
            db.add(AttendanceEvent(user_id=u.id, event="punch_in" if i % 2 == 0 else "punch_out",
                                   at=t + timedelta(seconds=i), source="backfill", created_at=t + timedelta(microseconds=i)))
        await db.commit()
    body = (await client.get(f"{BASE}/api/attendance/changes", params={"since": (t - timedelta(hours=1)).isoformat()},
                             headers={"x-api-key": KEY})).json()
    server_time = datetime.fromisoformat(body["server_time"])
    assert server_time <= datetime.now(timezone.utc)
    # next start = server_time - overlap: still before the last row read, so a slow commit is not skipped
    assert server_time - timedelta(seconds=60) <= t + timedelta(microseconds=99)


# ---------- Open check-ins in every poll (review: monitoring switched on days after the migration) ----------
async def test_every_poll_also_lists_who_is_checked_in_now(client):
    u = await _user()
    async with AsyncSessionLocal() as db:
        await att.check_in(db, await db.merge(u))  # real time: an open check-in right now
    # A poll whose cursor is long past that event still names it, by its own id
    later = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    body = (await client.get(f"{BASE}/api/attendance/changes", params={"since": later},
                             headers={"x-api-key": KEY})).json()
    ev = await _events(u.id)
    assert [c["id"] for c in body["changes"]] == [str(ev[-1].id)] and body["changes"][0]["event"] == "punch_in"


# ---------- Push: no polling wait ----------
class _Recorder:
    def __init__(self, fail: bool = False):
        self.calls: list[tuple[str, dict]] = []
        self.fail = fail

    def __call__(self, request: httpx.Request) -> httpx.Response:
        import json
        if self.fail:
            raise httpx.ConnectError("monitoring down")
        self.calls.append((request.url.path, json.loads(request.content)))
        assert request.headers["x-api-key"] == "push-key"
        return httpx.Response(200, json={"applied": 1})


@pytest.fixture
def monitoring_server(monkeypatch):
    def start(fail: bool = False) -> _Recorder:
        rec = _Recorder(fail)
        monkeypatch.setattr(settings, "MONITORING_BASE_URL", "http://mon-api:8000")
        monkeypatch.setattr(settings, "MONITORING_API_KEY", "push-key")
        monkeypatch.setattr(svc, "_client", httpx.AsyncClient(transport=httpx.MockTransport(rec),
                                                              base_url="http://mon-api:8000",
                                                              headers={"X-Api-Key": "push-key"}))
        return rec
    yield start


async def test_a_check_in_is_pushed_the_moment_it_is_saved(monitoring_server):
    rec = monitoring_server()
    u = await _user()
    async with AsyncSessionLocal() as db:
        await att.check_in(db, await db.merge(u))
    await svc.wait_for_pushes()
    att_calls = [b for p, b in rec.calls if p == "/api/crm/attendance/push"]
    assert len(att_calls) == 1
    assert [(c["employee_id"], c["event"]) for c in att_calls[0]["changes"]] == [(str(u.id), "punch_in")]


async def test_each_push_carries_the_recent_events_in_order(monitoring_server):
    """Two pushes may arrive in either order: each holds the person's recent events, oldest first."""
    rec = monitoring_server()
    u = await _user()
    for fn in (att.check_in, att.check_out):
        async with AsyncSessionLocal() as db:
            await fn(db, await db.merge(u))
    await svc.wait_for_pushes()
    last = [b for p, b in rec.calls if p == "/api/crm/attendance/push"][-1]
    assert [c["event"] for c in last["changes"]] == ["punch_in", "punch_out"]


async def test_a_failed_push_never_fails_the_punch(monitoring_server):
    monitoring_server(fail=True)
    u = await _user()
    async with AsyncSessionLocal() as db:
        await att.check_in(db, await db.merge(u))  # no error reaches the person
    await svc.wait_for_pushes()
    assert [e.event for e in await _events(u.id)] == ["punch_in"]  # saved; the poll will deliver it


async def test_nothing_is_pushed_for_a_rolled_back_punch(monitoring_server):
    rec = monitoring_server()
    u = await _user()
    async with AsyncSessionLocal() as db:
        await att.check_in(db, await db.merge(u))
    await svc.wait_for_pushes()
    rec.calls.clear()
    with pytest.raises(Exception):
        async with AsyncSessionLocal() as db:
            await att.check_in(db, await db.merge(u))  # already checked in: refused, rolled back
    await svc.wait_for_pushes()
    assert rec.calls == []


async def test_employee_changes_are_pushed_but_other_columns_are_not(monitoring_server):
    rec = monitoring_server()
    u = await _user()
    await svc.wait_for_pushes()
    rec.calls.clear()
    async with AsyncSessionLocal() as db:
        row = await db.get(User, u.id)
        row.firebase_checked_at = datetime.now(timezone.utc)  # changes on every session check: not pushed
        await db.commit()
    await svc.wait_for_pushes()
    assert rec.calls == []
    async with AsyncSessionLocal() as db:
        row = await db.get(User, u.id)
        row.status = "disabled"
        await db.commit()
    await svc.wait_for_pushes()
    assert rec.calls == [("/api/crm/employees/push", {"employees": [
        {"employee_id": str(u.id), "name": u.name, "email": u.email, "department": None,
         "manager_id": None, "backup_approver_id": None, "status": "disabled"}]})]


async def test_no_push_while_the_module_is_off(monitoring_server, monkeypatch):
    rec = monitoring_server()
    monkeypatch.setenv("KJS__MODULES__MONITORING", "off")
    ini.reload_now()
    u = await _user()
    async with AsyncSessionLocal() as db:
        await att.check_in(db, await db.merge(u))
    await svc.wait_for_pushes()
    assert rec.calls == []
