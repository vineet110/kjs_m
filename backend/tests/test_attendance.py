"""Attendance: punching, late rule, week view, regularization approval, permissions."""
from datetime import date, datetime, timezone

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

