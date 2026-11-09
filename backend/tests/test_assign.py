"""Auto-assign: import rules, who is eligible, one open batch, daily cap, working a batch."""
import io
from datetime import datetime, timezone

from openpyxl import Workbook
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.services import assign_service
from tests.conftest import HDR, login, make_user

CSV = (
    "Company,Contact,Email,Country,Category\n"
    "Al Noor Trading,Omar,omar@alnoor.ae,UAE,coffee\n"
    "Lagos Foods,Ada,,Nigeria,Coffee\n"
    ",Nobody,,India,coffee\n"
    "Tea House,Li,,China,tea\n"
)


async def _boss(client):
    await make_user("boss@kjsindia.com", permissions=["leads.view", "assign.manage"])
    await login(client, "boss@kjsindia.com")


async def _import(client, text=CSV, name="buyers.csv"):
    return await client.post("/api/v1/assign/import", files={"file": (name, text.encode(), "text/csv")}, headers=HDR)


async def _uid(email):
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(User.id).where(User.email == email))


async def test_import_csv_skips_bad_rows(client):
    await _boss(client)
    r = await _import(client)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["added"] == 2 and body["skipped_count"] == 2  # no company, unknown category "tea"
    assert {s["reason"] for s in body["skipped"]} == {"no company", "unknown category 'tea'"}


async def test_import_xlsx(client):
    await _boss(client)
    wb = Workbook()
    wb.active.append(["Company Name", "Phone", "Notes"])
    wb.active.append(["Dubai Mart", "+971 50 000 0000", "Met at Gulfood"])
    buf = io.BytesIO()
    wb.save(buf)
    r = await client.post("/api/v1/assign/import", data={"default_category": "coffee"},
                          files={"file": ("list.xlsx", buf.getvalue(), "application/octet-stream")}, headers=HDR)
    assert r.json()["added"] == 1


async def test_import_needs_company_column(client):
    await _boss(client)
    r = await _import(client, "Name of firm,Email\nX,y@z.com\n".replace("Name of firm", "Firm"))
    assert r.status_code == 422 and r.json()["code"] == "bad_file"


async def test_only_checked_in_available_staff_with_categories_get_batches(client):
    await _boss(client)
    await _import(client)
    await make_user("a@kjsindia.com")
    await make_user("b@kjsindia.com")
    a, b = await _uid("a@kjsindia.com"), await _uid("b@kjsindia.com")
    # categories for both; only a checks in
    for uid in (a, b):
        r = await client.post(f"/api/v1/assign/staff/{uid}/categories", json={"categories": ["coffee"]}, headers=HDR)
        assert r.status_code == 204
    assert (await client.get("/api/v1/assign/preview")).json() == []  # nobody checked in yet

    await login(client, "a@kjsindia.com")
    await client.post("/api/v1/attendance/check-in", headers=HDR)
    await login(client, "boss@kjsindia.com")
    plan = (await client.get("/api/v1/assign/preview")).json()
    assert [(p["name"], p["would_get"]) for p in plan] == [("a", 2)]
    r = await client.post("/api/v1/assign/run", headers=HDR)
    assert r.json()["given"] == [{"user_id": a, "name": "a", "records": 2}]
    # second run: a already has an open batch, nothing new to give
    assert (await client.post("/api/v1/assign/run", headers=HDR)).json()["batches"] == 0


async def test_work_through_batch(client):
    await _boss(client)
    await _import(client)
    await make_user("a@kjsindia.com")
    a = await _uid("a@kjsindia.com")
    await client.post(f"/api/v1/assign/staff/{a}/categories", json={"categories": ["coffee"]}, headers=HDR)
    await login(client, "a@kjsindia.com")
    await client.post("/api/v1/attendance/check-in", headers=HDR)
    async with AsyncSessionLocal() as db:
        await assign_service.run(db, None, datetime.now(timezone.utc))

    batch = (await client.get("/api/v1/assign/my-batches")).json()[0]
    assert batch["status"] == "open" and batch["size"] == 2
    first, second = batch["records"]
    r = await client.patch(f"/api/v1/assign/records/{first['id']}", json={"status": "done", "outcome": "Wants samples"}, headers=HDR)
    assert r.json()["left"] == 1 and r.json()["batch_status"] == "open"
    r = await client.patch(f"/api/v1/assign/records/{second['id']}", json={"status": "skipped", "outcome": "Closed down"}, headers=HDR)
    assert r.json()["batch_status"] == "done"
    assert (await client.get("/api/v1/employee/notifications")).json()["unread"] == 1


async def test_not_available_gets_nothing(client):
    await _boss(client)
    await _import(client)
    await make_user("a@kjsindia.com")
    a = await _uid("a@kjsindia.com")
    await client.post(f"/api/v1/assign/staff/{a}/categories", json={"categories": ["coffee"]}, headers=HDR)
    await login(client, "a@kjsindia.com")
    await client.post("/api/v1/attendance/check-in", headers=HDR)
    await client.post("/api/v1/attendance/availability", json={"available": False}, headers=HDR)
    async with AsyncSessionLocal() as db:
        assert (await assign_service.run(db))["batches"] == 0


async def test_someone_elses_record_is_hidden(client):
    await _boss(client)
    await _import(client)
    await make_user("a@kjsindia.com")
    await make_user("b@kjsindia.com")
    a = await _uid("a@kjsindia.com")
    await client.post(f"/api/v1/assign/staff/{a}/categories", json={"categories": ["coffee"]}, headers=HDR)
    await login(client, "a@kjsindia.com")
    await client.post("/api/v1/attendance/check-in", headers=HDR)
    async with AsyncSessionLocal() as db:
        await assign_service.run(db)
    rec = (await client.get("/api/v1/assign/my-batches")).json()[0]["records"][0]
    await login(client, "b@kjsindia.com")
    r = await client.patch(f"/api/v1/assign/records/{rec['id']}", json={"status": "done"}, headers=HDR)
    assert r.status_code == 404


async def test_admin_routes_need_assign_manage(client):
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    for method, path in (("get", "/api/v1/assign/overview"), ("get", "/api/v1/assign/preview"), ("post", "/api/v1/assign/run")):
        assert (await client.request(method, path, headers=HDR)).status_code == 403
    assert (await client.get("/api/v1/assign/my-batches")).json() == []


async def test_disabling_someone_gives_their_unfinished_buyers_back(client):
    """CR9: a disabled person's open batch used to be stuck for ever, and hidden."""
    from app.models.batch import Batch, BuyerRecord
    await make_user("admin@kjsindia.com", role="admin")
    await _boss(client)
    await _import(client)
    await make_user("a@kjsindia.com")
    a = await _uid("a@kjsindia.com")
    await client.post(f"/api/v1/assign/staff/{a}/categories", json={"categories": ["coffee"]}, headers=HDR)
    await login(client, "a@kjsindia.com")
    await client.post("/api/v1/attendance/check-in", headers=HDR)
    async with AsyncSessionLocal() as db:
        await assign_service.run(db, None, datetime.now(timezone.utc))
    first = (await client.get("/api/v1/assign/my-batches")).json()[0]["records"][0]
    await client.patch(f"/api/v1/assign/records/{first['id']}", json={"status": "done", "outcome": "Called"}, headers=HDR)

    await login(client, "admin@kjsindia.com")
    assert (await client.post(f"/api/v1/admin/users/{a}/status", json={"status": "disabled"}, headers=HDR)).status_code == 200
    async with AsyncSessionLocal() as db:
        batch = await db.scalar(select(Batch).where(Batch.user_id == a))
        recs = (await db.scalars(select(BuyerRecord).order_by(BuyerRecord.id))).all()
    assert batch.status == "returned"  # not "done": half of it was never worked on
    assert sorted(r.status for r in recs if r.id != first["id"] and r.category == "coffee") == ["new"]
    assert next(r for r in recs if r.id == first["id"]).status == "done"  # finished work stays finished
