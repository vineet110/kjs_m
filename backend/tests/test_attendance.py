"""Attendance: punching, late rule, week view, regularization approval, permissions."""
from datetime import date, datetime, timezone

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.services import attendance_service as svc
from tests.conftest import HDR, login, make_user


def ist(d: str, hhmm: str) -> datetime:
    return svc.to_utc(date.fromisoformat(d), hhmm)


def test_punch_status_without_late_penalty():
    # Removal of late penalty and grace time: all punches count as present
    assert svc.punch_status(ist("2026-10-26", "09:44")) == "present"
    assert svc.punch_status(ist("2026-10-26", "09:46")) == "present"
    assert svc.punch_status(ist("2026-10-26", "11:30")) == "present"


async def _user(email="e@kjsindia.com", joined_on=None) -> User:
    await make_user(email)
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        u = await db.scalar(select(User).where(User.email == email))
        if joined_on:
            u.joined_on = joined_on
            await db.commit()
            await db.refresh(u)
        return u


async def test_check_in_out_and_week():
    u = await _user(joined_on=date(2026, 10, 26))
    async with AsyncSessionLocal() as db:
        u = await db.merge(u)
        await svc.check_in(db, u, now=ist("2026-10-26", "09:50"))
        await svc.check_out(db, u, now=ist("2026-10-26", "18:20"))
        w = await svc.week(db, u.id, date(2026, 10, 28), now=ist("2026-10-28", "12:00"))
    assert w["week_start"] == date(2026, 10, 26)
    mon, tue, wed, sun = w["days"][0], w["days"][1], w["days"][2], w["days"][6]
    assert (mon["state"], mon["check_in"], mon["check_out"], mon["hours"]) == ("present", "09:50", "18:20", 8.5)
    assert tue["state"] == "absent" and wed["state"] == "upcoming" and sun["state"] == "off"
    assert w["summary"]["present"] == 1 and w["summary"]["absent"] == 1


async def test_multi_punch_hours_calculation():
    u = await _user(email="multipunch@kjsindia.com", joined_on=date(2026, 10, 26))
    async with AsyncSessionLocal() as db:
        u = await db.merge(u)
        # Session 1: 09:00 - 13:00 (4.0 hrs)
        await svc.check_in(db, u, now=ist("2026-10-26", "09:00"))
        await svc.check_out(db, u, now=ist("2026-10-26", "13:00"))
        # Session 2: 14:00 - 18:30 (4.5 hrs)
        await svc.check_in(db, u, now=ist("2026-10-26", "14:00"))
        await svc.check_out(db, u, now=ist("2026-10-26", "18:30"))

        today_info = await svc.today(db, u, now=ist("2026-10-26", "19:00"))
        w = await svc.week(db, u.id, date(2026, 10, 26), now=ist("2026-10-26", "19:00"))

    # Total hours should be 4.0 + 4.5 = 8.5 hrs
    assert today_info["hours"] == 8.5
    assert today_info["check_in"] == "09:00"
    assert today_info["check_out"] == "18:30"
    assert len(today_info["punches"]) == 4

    mon = w["days"][0]
    assert mon["hours"] == 8.5
    assert len(mon["punches"]) == 4
    assert mon["check_in"] == "09:00"
    assert mon["check_out"] == "18:30"


async def test_new_joiner_past_days_not_absent():
    # Joined on Wednesday Oct 28
    u = await _user(email="newjoiner@kjsindia.com", joined_on=date(2026, 10, 28))
    async with AsyncSessionLocal() as db:
        u = await db.merge(u)
        w = await svc.week(db, u.id, date(2026, 10, 28), now=ist("2026-10-28", "12:00"))
    mon, tue, wed = w["days"][0], w["days"][1], w["days"][2]
    # Monday and Tuesday before joined_on are 'not_joined', NOT 'absent'
    assert mon["state"] == "not_joined"
    assert tue["state"] == "not_joined"
    assert wed["state"] == "upcoming"
    assert w["summary"]["absent"] == 0
    assert w["summary"]["not_joined"] == 2


async def test_double_check_in_rejected(client):
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    assert (await client.post("/api/v1/attendance/check-in", headers=HDR)).status_code == 200
    r = await client.post("/api/v1/attendance/check-in", headers=HDR)
    assert r.status_code == 409 and r.json()["code"] == "already_checked_in"
    r = await client.post("/api/v1/attendance/check-out", headers=HDR)
    assert r.status_code == 200 and r.json()["check_out"]


async def test_check_out_needs_check_in(client):
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    r = await client.post("/api/v1/attendance/check-out", headers=HDR)
    assert r.status_code == 409 and r.json()["code"] == "not_checked_in"


async def test_availability_toggle(client):
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    r = await client.post("/api/v1/attendance/availability", json={"available": False}, headers=HDR)
    assert r.json() == {"is_available": False}
    assert (await client.get("/api/v1/attendance/today")).json()["is_available"] is False


async def test_regularization_flow(client):
    await make_user("e@kjsindia.com")
    await make_user("m@kjsindia.com", permissions=["attendance.manage"])
    await login(client, "e@kjsindia.com")
    body = {"day": "2026-10-20", "check_in": "09:30", "check_out": "18:30", "reason": "Forgot to punch"}
    r = await client.post("/api/v1/attendance/regularizations", json=body, headers=HDR)
    assert r.status_code == 201, r.text
    reg_id = r.json()["id"]
    assert (await client.post("/api/v1/attendance/regularizations", json=body, headers=HDR)).status_code == 409
    # the employee can't approve (no permission)
    assert (await client.post(f"/api/v1/attendance/approvals/{reg_id}", json={"approve": True}, headers=HDR)).status_code == 403

    await login(client, "m@kjsindia.com")
    pending = (await client.get("/api/v1/attendance/approvals")).json()
    assert [p["id"] for p in pending] == [reg_id]
    r = await client.post(f"/api/v1/attendance/approvals/{reg_id}", json={"approve": True}, headers=HDR)
    assert r.json()["status"] == "approved"
    again = await client.post(f"/api/v1/attendance/approvals/{reg_id}", json={"approve": True}, headers=HDR)
    assert again.status_code == 409

    await login(client, "e@kjsindia.com")
    w = (await client.get("/api/v1/attendance/week?start=2026-10-19")).json()
    tue = w["days"][1]
    assert (tue["state"], tue["check_in"], tue["check_out"]) == ("present", "09:30", "18:30")


async def test_regularization_rejects_bad_times(client):
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    body = {"day": "2026-10-20", "check_in": "18:30", "check_out": "09:30", "reason": "oops"}
    r = await client.post("/api/v1/attendance/regularizations", json=body, headers=HDR)
    assert r.status_code == 422 and r.json()["code"] == "bad_times"


async def test_team_view_needs_permission(client):
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    assert (await client.get("/api/v1/attendance/team")).status_code == 403
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    r = await client.get("/api/v1/attendance/team")
    assert r.status_code == 200 and {x["name"] for x in r.json()} >= {"e"}


async def test_not_logged_in(client):
    assert (await client.get("/api/v1/attendance/today")).status_code == 401


async def test_leave_application_and_approval(client):
    await make_user("employee@kjsindia.com")
    await make_user("admin@kjsindia.com", role="admin")

    # 1. Employee requests leave
    await login(client, "employee@kjsindia.com")
    req = {
        "leave_type": "casual",
        "start_date": "2026-11-10",
        "end_date": "2026-11-11",
        "reason": "Family function",
    }
    r = await client.post("/api/v1/attendance/leaves", json=req, headers=HDR)
    assert r.status_code == 201
    leave_id = r.json()["id"]
    assert r.json()["working_days"] == 2

    # 2. Admin views pending leaves
    await login(client, "admin@kjsindia.com")
    r_list = await client.get("/api/v1/attendance/leaves/approvals", headers=HDR)
    assert r_list.status_code == 200
    assert any(item["id"] == leave_id for item in r_list.json())

    # 3. Admin approves leave
    r_decide = await client.post(f"/api/v1/attendance/leaves/approvals/{leave_id}", json={"approve": True}, headers=HDR)
    assert r_decide.status_code == 200
    assert r_decide.json()["status"] == "approved"

    # 4. Check that attendance has status="leave" on that day
    async with AsyncSessionLocal() as db:
        from app.models.attendance import Attendance
        from sqlalchemy import select
        att = await db.scalar(select(Attendance).where(Attendance.day == date(2026, 11, 10)))
        assert att is not None
        assert att.status == "leave"
        assert att.source == "leave"


async def test_shift_creation_and_assignment(client):
    await make_user("admin_shift@kjsindia.com", role="admin")
    worker = await _user("worker_shift@kjsindia.com")
    await login(client, "admin_shift@kjsindia.com")

    # Create special shift
    shift_data = {
        "name": "Afternoon Shift",
        "code": "AFT",
        "start_time": "12:00",
        "end_time": "20:30",
        "is_night_shift": False
    }
    r = await client.post("/api/v1/attendance/shifts", json=shift_data, headers=HDR)
    assert r.status_code == 201
    shift_id = r.json()["id"]

    # Assign to worker
    r_assign = await client.post("/api/v1/attendance/shifts/assign", json={"user_id": worker.id, "shift_id": shift_id}, headers=HDR)
    assert r_assign.status_code == 200

    # Worker checks today() and sees their assigned shift
    await login(client, "worker_shift@kjsindia.com")
    r_today = await client.get("/api/v1/attendance/today", headers=HDR)
    assert r_today.status_code == 200
    assert r_today.json()["shift_name"] == "Afternoon Shift"
    assert r_today.json()["shift"] == "12:00–20:30"


async def test_excel_export_endpoint(client):
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    r = await client.get("/api/v1/attendance/export?start_date=2026-11-01&end_date=2026-11-07", headers=HDR)
    assert r.status_code == 200
    assert "spreadsheetml.sheet" in r.headers["content-type"]
    assert len(r.content) > 1000  # Valid Excel binary file


async def test_multi_punch_per_shift(client):
    await make_user("puncher@kjsindia.com")
    await login(client, "puncher@kjsindia.com")
    # 1. First punch in
    r1 = await client.post("/api/v1/attendance/check-in", headers=HDR)
    assert r1.status_code == 200

    # 2. Duplicate punch in rejected
    r_dup = await client.post("/api/v1/attendance/check-in", headers=HDR)
    assert r_dup.status_code == 409 and r_dup.json()["code"] == "already_checked_in"

    # 3. First punch out (e.g. for lunch / break)
    r2 = await client.post("/api/v1/attendance/check-out", headers=HDR, json={"notes": "lunch"})
    assert r2.status_code == 200

    # 4. Duplicate punch out rejected
    r_dup_out = await client.post("/api/v1/attendance/check-out", headers=HDR)
    assert r_dup_out.status_code == 409 and r_dup_out.json()["code"] == "already_checked_out"

    # 5. Punch in again as per employee choice -> allowed!
    r3 = await client.post("/api/v1/attendance/check-in", headers=HDR)
    assert r3.status_code == 200

    # 6. Punch out again -> allowed!
    r4 = await client.post("/api/v1/attendance/check-out", headers=HDR, json={"notes": "end of day"})
    assert r4.status_code == 200

    # 7. Check today endpoint returns multiple punches
    today_resp = await client.get("/api/v1/attendance/today", headers=HDR)
    assert today_resp.status_code == 200
    data = today_resp.json()
    assert data["is_checked_in"] is False
    assert len(data["punches"]) == 4
    assert [p["type"] for p in data["punches"]] == ["in", "out", "in", "out"]


async def test_month_and_holiday_input_validation(client):
    await make_user("validator@kjsindia.com")
    await login(client, "validator@kjsindia.com")
    # Invalid month > 12
    r_bad_month = await client.get("/api/v1/attendance/month?year=2026&month=13", headers=HDR)
    assert r_bad_month.status_code == 422
    # Invalid month < 1
    r_bad_month0 = await client.get("/api/v1/attendance/month?year=2026&month=0", headers=HDR)
    assert r_bad_month0.status_code == 422
    # Invalid year
    r_bad_year = await client.get("/api/v1/attendance/month?year=1990&month=5", headers=HDR)
    assert r_bad_year.status_code == 422


async def test_excel_export_range_limit(client):
    await make_user("admin_export@kjsindia.com", role="admin")
    await login(client, "admin_export@kjsindia.com")
    # Range of 400 days (> 366 limit)
    r = await client.get("/api/v1/attendance/export?start_date=2025-01-01&end_date=2026-02-15", headers=HDR)
    assert r.status_code == 422
    assert r.json()["code"] == "range_too_large"


async def test_half_day_leave_validation(client):
    await make_user("half_day_user@kjsindia.com")
    await login(client, "half_day_user@kjsindia.com")

    # 1. Multi-day half-day rejected
    r1 = await client.post("/api/v1/attendance/leaves", headers=HDR, json={
        "leave_type": "casual", "start_date": "2026-11-10", "end_date": "2026-11-12",
        "reason": "Doctor", "is_half_day": True, "half_day_session": "first_half"
    })
    assert r1.status_code == 422 and r1.json()["code"] == "bad_half_day"

    # 2. Bad session rejected
    r2 = await client.post("/api/v1/attendance/leaves", headers=HDR, json={
        "leave_type": "casual", "start_date": "2026-11-10", "end_date": "2026-11-10",
        "reason": "Doctor", "is_half_day": True, "half_day_session": "midnight"
    })
    assert r2.status_code == 422 and r2.json()["code"] == "bad_session"

    # 3. Sunday half-day rejected (2026-11-08 is Sunday)
    r3 = await client.post("/api/v1/attendance/leaves", headers=HDR, json={
        "leave_type": "casual", "start_date": "2026-11-08", "end_date": "2026-11-08",
        "reason": "Doctor", "is_half_day": True, "half_day_session": "first_half"
    })
    assert r3.status_code == 422 and r3.json()["code"] == "no_working_days"

    # 4. Valid half-day creates 0.5 working days
    r4 = await client.post("/api/v1/attendance/leaves", headers=HDR, json={
        "leave_type": "sick", "start_date": "2026-11-10", "end_date": "2026-11-10",
        "reason": "Doctor appointment", "is_half_day": True, "half_day_session": "first_half"
    })
    assert r4.status_code == 201
    assert r4.json()["working_days"] == 0.5


async def test_leave_approval_does_not_overwrite_check_in(client):
    u = await _user("punctual@kjsindia.com")
    await make_user("admin_leave_approver@kjsindia.com", role="admin")

    # Employee already has an actual check-in punch on 2026-11-12
    async with AsyncSessionLocal() as db:
        from app.models.attendance import Attendance
        att = Attendance(
            user_id=u.id,
            day=date(2026, 11, 12),
            check_in_at=datetime(2026, 11, 12, 4, 30, tzinfo=timezone.utc),  # 10:00 AM IST
            status="present",
            source="punch"
        )
        db.add(att)
        await db.commit()

    # Leave request covering that day
    await login(client, "punctual@kjsindia.com")
    r_leave = await client.post("/api/v1/attendance/leaves", headers=HDR, json={
        "leave_type": "casual", "start_date": "2026-11-12", "end_date": "2026-11-12",
        "reason": "Emergency"
    })
    leave_id = r_leave.json()["id"]

    # Admin approves
    await login(client, "admin_leave_approver@kjsindia.com")
    r_appr = await client.post(f"/api/v1/attendance/leaves/approvals/{leave_id}", headers=HDR, json={"approve": True})
    assert r_appr.status_code == 200

    # Verify that attendance row was NOT overwritten: still present with check_in_at
    async with AsyncSessionLocal() as db:
        from app.models.attendance import Attendance
        row = await db.scalar(select(Attendance).where(Attendance.user_id == u.id, Attendance.day == date(2026, 11, 12)))
        assert row.status == "present"
        assert row.check_in_at is not None




async def _approve_fix(u: User, day: str, check_in: str, check_out: str | None):
    """A regularization for `day`, approved by a manager (service level)."""
    from app.models.attendance import Regularization
    await make_user("boss@kjsindia.com", permissions=["attendance.manage"])
    async with AsyncSessionLocal() as db:
        reg = Regularization(user_id=u.id, day=date.fromisoformat(day), check_in_at=ist(day, check_in),
                             check_out_at=ist(day, check_out) if check_out else None, reason="fix", status="pending")
        db.add(reg)
        await db.commit()
        boss = await db.scalar(select(User).where(User.email == "boss@kjsindia.com"))
        return await svc.decide(db, boss, reg.id, True)


async def test_a_fix_keeps_the_break_and_the_old_total_in_the_audit():
    """Review finding: approving a fix used to set hours = last out - first in (lunch counted as work)."""
    from app.models.audit import AuditLog
    u = await _user(email="lunch@kjsindia.com", joined_on=date(2026, 10, 26))
    async with AsyncSessionLocal() as db:
        u = await db.merge(u)
        for at, fn in (("09:00", svc.check_in), ("13:00", svc.check_out), ("14:00", svc.check_in), ("18:00", svc.check_out)):
            await fn(db, u, now=ist("2026-10-26", at))
    await _approve_fix(u, "2026-10-26", "08:30", None)  # "I came at 8:30, the check-in was late"
    async with AsyncSessionLocal() as db:
        info = await svc.today(db, await db.merge(u), now=ist("2026-10-26", "19:00"))
        audit = await db.scalar(select(AuditLog).where(AuditLog.action == "attendance.regularized"))
    assert (info["check_in"], info["check_out"], info["hours"]) == ("08:30", "18:00", 8.5)  # 4.5 + 4, lunch not counted
    assert [p["type"] for p in info["punches"]] == ["in", "out", "in", "out"]
    assert audit.before["hours"] == 8.0 and audit.after["hours"] == 8.5


async def test_a_fix_closes_a_day_left_open():
    u = await _user(email="open@kjsindia.com", joined_on=date(2026, 10, 26))
    async with AsyncSessionLocal() as db:
        await svc.check_in(db, await db.merge(u), now=ist("2026-10-26", "09:00"))
    await _approve_fix(u, "2026-10-26", "09:00", "18:00")
    async with AsyncSessionLocal() as db:
        info = await svc.today(db, await db.merge(u), now=ist("2026-10-26", "19:00"))
    assert (info["check_out"], info["hours"]) == ("18:00", 9.0)


async def test_double_taps_store_one_punch():
    """Two taps at the same moment: one punch, the other a clear 'already' answer (not an error 500)."""
    import asyncio
    from app.core.errors import AppError
    from app.models.attendance import AttendancePunch
    u = await _user(email="tap@kjsindia.com", joined_on=date(2026, 10, 26))

    async def tap(fn, at):
        async with AsyncSessionLocal() as db:
            try:
                await fn(db, await db.merge(u), now=ist("2026-10-26", at))
                return "ok"
            except AppError as e:
                return e.code

    assert sorted(await asyncio.gather(tap(svc.check_in, "09:00"), tap(svc.check_in, "09:00"))) == ["already_checked_in", "ok"]
    assert sorted(await asyncio.gather(tap(svc.check_out, "18:00"), tap(svc.check_out, "18:00"))) == ["already_checked_out", "ok"]
    async with AsyncSessionLocal() as db:
        kinds = (await db.scalars(select(AttendancePunch.punch_type).where(AttendancePunch.user_id == u.id))).all()
    assert sorted(kinds) == ["in", "out"]
