"""Bulk import: each row of an Excel / CSV file becomes an internal lead (preview first, then import)."""
from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.models.audit import AuditLog
from app.models.lead import Lead
from tests.conftest import HDR, login, make_user

PREVIEW = "/api/v1/employee/leads/import/preview"
IMPORT = "/api/v1/employee/leads/import"
CSV = (b"Name,Mobile,Company,Email\n"
       b"Ravi,+91 90000 11111,Ravi Traders,ravi@x.in\n"
       b"Neha,+91 90000 22222,Neha Foods,not-an-email\n"  # bad email
       b",+91 90000 33333,No Name Ltd,\n"  # no name
       b"Ravi again,+91 9000011111,Ravi Traders,\n")  # same phone as row 1


async def _staff(client, email="a@kjs.in"):
    await make_user(email)
    await login(client, email)


async def _count(model) -> int:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(func.count(model.id)))


async def test_preview_checks_every_row_and_saves_nothing(client):
    await _staff(client)
    r = await client.post(PREVIEW, files={"file": ("buyers.csv", CSV, "text/csv")}, headers=HDR)
    assert r.status_code == 200, r.text
    rows = r.json()["rows"]
    assert len(rows) == 4
    assert rows[0]["problems"] == [] and rows[0]["duplicate"] is None
    assert any(p.startswith("Email") for p in rows[1]["problems"])
    assert any(p.startswith("Name") for p in rows[2]["problems"])
    assert rows[3]["duplicate"] == "file"  # same phone as an earlier row
    assert await _count(Lead) == 0


async def test_preview_marks_people_already_in_our_leads(client):
    await _staff(client)
    lead = {"name": "Ravi", "phone": "+91 90000 11111"}
    assert (await client.post("/api/v1/employee/leads", json=lead, headers=HDR)).status_code == 201
    rows = (await client.post(PREVIEW, files={"file": ("b.csv", CSV, "text/csv")}, headers=HDR)).json()["rows"]
    assert rows[0]["duplicate"] == "existing"


async def test_import_creates_every_lead_mine_and_audited(client):
    await _staff(client)
    leads = [{"name": "Ravi", "phone": "+91 90000 11111", "category_slug": "coffee"},
             {"name": "Neha", "phone": "+91 90000 22222", "email": "neha@x.in"}]
    r = await client.post(IMPORT, json={"leads": leads}, headers=HDR)
    assert r.status_code == 201 and r.json()["created"] == 2
    mine = (await client.get("/api/v1/employee/leads?source=internal")).json()
    assert sorted(x["name"] for x in mine) == ["Neha", "Ravi"]
    async with AsyncSessionLocal() as db:
        actions = (await db.scalars(select(AuditLog.action))).all()
        assert actions.count("lead.created") == 2 and actions.count("lead.imported") == 1
        assert all(x.category_id for x in (await db.scalars(select(Lead).where(Lead.name == "Ravi"))).all())


async def test_import_is_all_or_nothing(client):
    await _staff(client)
    leads = [{"name": "Ravi", "phone": "+91 90000 11111"}, {"name": "X", "phone": "+91 90000 22222"}]  # name too short
    r = await client.post(IMPORT, json={"leads": leads}, headers=HDR)
    assert r.status_code == 422
    assert await _count(Lead) == 0


async def test_import_limits(client):
    await _staff(client)
    assert (await client.post(IMPORT, json={"leads": []}, headers=HDR)).status_code == 422
    too_many = [{"name": f"Buyer {i}", "phone": f"+91 90000 {i:05d}"} for i in range(501)]
    assert (await client.post(IMPORT, json={"leads": too_many}, headers=HDR)).status_code == 422
    big = b"Name,Phone\n" + b"".join(b"B%d,+91 90000 %05d\n" % (i, i) for i in range(501))
    r = await client.post(PREVIEW, files={"file": ("big.csv", big, "text/csv")}, headers=HDR)
    assert r.status_code == 422 and r.json()["code"] == "too_many_rows"  # never cut silently


async def test_empty_lines_do_not_hide_rows(client):
    """Empty lines between rows (common in Excel exports) must not push real rows past the limit unseen."""
    await _staff(client)
    gappy = b"Name,Phone\n" + b"".join(b"B%d,+91 90000 %05d\n,\n" % (i, i) for i in range(501))
    r = await client.post(PREVIEW, files={"file": ("gappy.csv", gappy, "text/csv")}, headers=HDR)
    assert r.status_code == 422 and r.json()["code"] == "too_many_rows"
    ok = b"Name,Phone\n" + b"".join(b"B%d,+91 90000 %05d\n,\n,\n" % (i, i) for i in range(400))
    r = await client.post(PREVIEW, files={"file": ("ok.csv", ok, "text/csv")}, headers=HDR)
    assert r.status_code == 200 and len(r.json()["rows"]) == 400


async def test_import_needs_login(client):
    r = await client.post(IMPORT, json={"leads": [{"name": "Ravi", "phone": "+91 90000 11111"}]}, headers=HDR)
    assert r.status_code == 401
