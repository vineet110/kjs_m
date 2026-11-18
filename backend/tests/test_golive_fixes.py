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
