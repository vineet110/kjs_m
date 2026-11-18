"""Go-live review fixes (18 Nov): who may create accounts, who sees company-wide lead numbers, and the
"forbidden" cases for lead and auto-assign routes that had only an "allowed" test."""
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.lead import Lead
from app.models.user import User
from tests.conftest import HDR, login, make_user

ENQ = {"name": "Omar", "email": "omar@alnoor.ae", "consent": True, "phone": "+91 98765 43210", "message": "Need sticks"}
NEHA = {"name": "Neha", "email": "neha@kjsindia.com", "phone": "+91 98765 43210", "role": "employee",
        "employee_code": "KJS-020", "branch": "Mumbai"}


async def _uid(email: str) -> int:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(User.id).where(User.email == email))


async def _leads_of(email: str) -> int:
    async with AsyncSessionLocal() as db:
        return len((await db.scalars(select(Lead).where(Lead.assigned_to == await _uid(email)))).all())


# ---------- Creating an account (User Creation Form) ----------
async def test_approver_cannot_create_an_account(client):
    await make_user("appr@kjsindia.com", permissions=["leads.view", "staff.approve"])
    await login(client, "appr@kjsindia.com")
    r = await client.post("/api/v1/admin/users", json=NEHA, headers=HDR)
    assert r.status_code == 403 and r.json()["code"] == "forbidden"
    assert await _uid("neha@kjsindia.com") is None  # nothing was made


async def test_admin_can_create_an_account(client):
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    assert (await client.post("/api/v1/admin/users", json=NEHA, headers=HDR)).status_code == 201


# ---------- Overview lead numbers ----------
async def test_overview_hides_lead_numbers_without_view_all(client):
    await client.post("/api/v1/public/leads", json=ENQ, headers=HDR)
    await make_user("appr@kjsindia.com", permissions=["leads.view", "staff.approve"])
    await login(client, "appr@kjsindia.com")
    s = (await client.get("/api/v1/admin/stats")).json()
    assert s["leads_total"] is None and s["leads_new"] is None and s["leads_this_week"] is None
    assert s["staff_active"] >= 1  # the rest of the overview still works


async def test_overview_shows_lead_numbers_with_view_all(client):
    await client.post("/api/v1/public/leads", json=ENQ, headers=HDR)
    await make_user("mgr@kjsindia.com", permissions=["leads.view", "staff.approve", "leads.view_all"])
    await login(client, "mgr@kjsindia.com")
    s = (await client.get("/api/v1/admin/stats")).json()
    assert s["leads_total"] == 1 and s["leads_new"] == 1 and s["leads_this_week"] == 1


# ---------- Another person's lead: no change through the API ----------
async def _lead_owned_by_b(client) -> int:
    """A web lead that employee B has taken (by marking it contacted). Ends logged in as A."""
    await client.post("/api/v1/public/leads", json=ENQ, headers=HDR)
    await make_user("a@kjsindia.com")
    await make_user("b@kjsindia.com")
    await login(client, "b@kjsindia.com")
    lead_id = (await client.get("/api/v1/employee/leads")).json()[0]["id"]
    r = await client.patch(f"/api/v1/employee/leads/{lead_id}", json={"status": "contacted"}, headers=HDR)
    assert r.status_code == 204
    await client.post("/api/v1/auth/logout", headers=HDR)
    await login(client, "a@kjsindia.com")
    return lead_id


async def test_employee_cannot_change_status_of_anothers_lead(client):
    lead_id = await _lead_owned_by_b(client)
    r = await client.patch(f"/api/v1/employee/leads/{lead_id}", json={"status": "closed", "outcome": "spam"}, headers=HDR)
    assert r.status_code == 404
    async with AsyncSessionLocal() as db:
        assert (await db.get(Lead, lead_id)).status == "contacted"


async def test_employee_cannot_add_note_to_anothers_lead(client):
    lead_id = await _lead_owned_by_b(client)
    r = await client.post(f"/api/v1/employee/leads/{lead_id}/notes", json={"kind": "note", "text": "hi"}, headers=HDR)
    assert r.status_code == 404


async def test_employee_cannot_hand_over_anothers_lead(client):
    lead_id = await _lead_owned_by_b(client)
    r = await client.post(f"/api/v1/employee/leads/{lead_id}/handover", json={"user_id": await _uid("a@kjsindia.com")},
                          headers=HDR)
    assert r.status_code == 404
    assert await _leads_of("b@kjsindia.com") == 1  # still B's


# ---------- Auto-assign admin routes ----------
async def test_assign_import_needs_assign_manage(client):
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    files = {"file": ("buyers.csv", b"name,phone\nRavi,+91 90000 11111\n", "text/csv")}
    r = await client.post("/api/v1/assign/import", files=files, headers=HDR)
    assert r.status_code == 403 and r.json()["details"]["needs"] == "assign.manage"


async def test_assign_categories_needs_assign_manage(client):
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    me = await _uid("e@kjsindia.com")
    r = await client.post(f"/api/v1/assign/staff/{me}/categories", json={"categories": ["coffee"]}, headers=HDR)
    assert r.status_code == 403 and r.json()["details"]["needs"] == "assign.manage"


# ---------- Lead lists: pages (config/leads.ini employee_page_size / admin_page_size) ----------
async def _many_leads(n: int) -> None:
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        for i in range(n):  # lead 0 is the newest
            db.add(Lead(source="enquiry_form", name=f"Buyer {i}", phone=f"+91 90000 {i:05d}", consent=True,
                        consent_at=now, created_at=now - timedelta(minutes=i)))
        await db.commit()


def _page_size(monkeypatch, key: str, value: int) -> None:
    from app.core.config import ini
    monkeypatch.setenv(f"KJS__LEADS__{key.upper()}", str(value))
    ini.reload_now()


async def test_employee_reaches_older_unassigned_leads_on_the_next_page(client, monkeypatch):
    _page_size(monkeypatch, "employee_page_size", 50)
    await _many_leads(60)
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    first = (await client.get("/api/v1/employee/leads")).json()
    second = (await client.get("/api/v1/employee/leads?offset=50")).json()
    assert len(first) == 50 and len(second) == 10
    assert second[-1]["name"] == "Buyer 59"  # the oldest one is reachable
    assert not {r["id"] for r in first} & {r["id"] for r in second}  # no lead twice


async def test_admin_page_size_comes_from_config(client, monkeypatch):
    _page_size(monkeypatch, "admin_page_size", 50)
    await _many_leads(55)
    await make_user("admin@kjsindia.com", role="admin")
    me = (await login(client, "admin@kjsindia.com")).json()
    assert me["limits"]["leads_page_admin"] == 50  # the portal knows when a page is full
    assert len((await client.get("/api/v1/admin/leads")).json()) == 50
    assert len((await client.get("/api/v1/admin/leads?offset=50")).json()) == 5


def test_page_size_out_of_bounds_is_refused(monkeypatch):
    from app.core.config import ini
    monkeypatch.setenv("KJS__LEADS__EMPLOYEE_PAGE_SIZE", "5")  # below 50
    c = ini.reload_now()
    assert c.leads.employee_page_size == 200  # refused: the last good value stays
