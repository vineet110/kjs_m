"""Portal and admin fixes from the 26 Nov UAT test run (go-live PR 3). One test per problem."""
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.lead import Lead
from app.models.user import User
from tests.conftest import HDR, login, make_user


async def _uid(email: str) -> int:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(User.id).where(User.email == email))


async def test_holiday_name_needs_two_letters(client):  # TC-SET-08
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    r = await client.post("/api/v1/admin/holidays", json={"day": "2027-01-26", "name": " a "}, headers=HDR)
    assert r.status_code == 422
    r = await client.post("/api/v1/admin/holidays", json={"day": "2027-01-26", "name": "Republic Day"}, headers=HDR)
    assert r.status_code in (200, 201)


async def test_attendance_export_counts_both_days(client):  # TC-ATT-14
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    ok = await client.get("/api/v1/attendance/export?start_date=2025-01-01&end_date=2026-01-01", headers=HDR)
    assert ok.status_code == 200  # 366 days
    r = await client.get("/api/v1/attendance/export?start_date=2025-01-01&end_date=2026-01-02", headers=HDR)
    assert r.status_code == 422 and r.json()["code"] == "range_too_large"  # 367 days


async def test_profile_photo_must_be_a_picture(client):  # TC-PROF-06
    await make_user("a@kjsindia.com")
    await login(client, "a@kjsindia.com")
    me = await _uid("a@kjsindia.com")
    gif = b"GIF89a\x01\x00\x01\x00\x00\x00\x00;"
    r = await client.post("/api/v1/files", data={"owner_type": "user", "owner_id": str(me)},
                          files={"file": ("me.gif", gif, "image/gif")}, headers=HDR)
    assert r.status_code == 422 and r.json()["code"] == "file_type"


async def test_a_lead_cannot_be_closed_without_an_outcome(client):
    await make_user("e@kjsindia.com", permissions=["leads.view"])
    assert (await client.post("/api/v1/public/leads", json={
        "name": "Omar", "email": "omar@alnoor.ae", "consent": True, "phone": "+91 98765 43210"})).status_code == 201
    await login(client, "e@kjsindia.com")
    async with AsyncSessionLocal() as db:
        lead_id = await db.scalar(select(Lead.id))
    r = await client.patch(f"/api/v1/employee/leads/{lead_id}", json={"status": "closed", "outcome": " "}, headers=HDR)
    assert r.status_code == 422 and r.json()["code"] == "outcome_required"
    r = await client.patch(f"/api/v1/employee/leads/{lead_id}", json={"status": "closed", "outcome": "Won"}, headers=HDR)
    assert r.status_code == 204
