"""Staff management (feat/employee-permissions): reject sign-ups with a reason, approved / rejected lists,
editing an approved employee's permissions (admin only), job titles, and "Admin access"."""
from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.conftest import HDR, login, make_user

ADMIN = "admin@kjs.test"
API = "/api/v1/admin"


async def _signup(client, email="new@kjs.test", name="New Person"):
    r = await client.post("/api/v1/auth/signup", headers=HDR,
                          json={"name": name, "email": email, "phone": "+91 98765 43210", "password": "password1234"})
    assert r.status_code in (200, 201), r.text


async def _id(client, email):
    return next(u["id"] for u in (await client.get(f"{API}/users", headers=HDR)).json() if u["email"] == email)


async def _as(email):
    c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    await login(c, email)
    return c


# ---------------------------------------------------------------- reject
async def test_reject_needs_a_reason_and_is_listed_and_audited(client):
    await make_user(ADMIN, role="admin")
    await _signup(client)
    await login(client, ADMIN)
    uid = await _id(client, "new@kjs.test")
    r = await client.post(f"{API}/users/{uid}/reject", headers=HDR, json={"reason": ""})
    assert r.status_code == 422  # reason is required
    r = await client.post(f"{API}/users/{uid}/reject", headers=HDR, json={"reason": "Not a KJS employee"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "rejected" and r.json()["rejection_reason"] == "Not a KJS employee"
    inbox = (await client.get(f"{API}/approvals", headers=HDR)).json()
    assert inbox["signups"] == []
    assert [u["email"] for u in inbox["rejected"]] == ["new@kjs.test"]
    assert inbox["rejected"][0]["decided_by_name"] and inbox["rejected"][0]["rejection_reason"] == "Not a KJS employee"
    actions = [a["action"] for a in (await client.get(f"{API}/audit", headers=HDR)).json()]
    assert "user.rejected" in actions


async def test_rejected_person_cannot_log_in(client):
    await make_user(ADMIN, role="admin")
    await _signup(client)
    await login(client, ADMIN)
    uid = await _id(client, "new@kjs.test")
    await client.post(f"{API}/users/{uid}/reject", headers=HDR, json={"reason": "Duplicate account"})
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as other:
        r = await other.post("/api/v1/auth/login", headers=HDR, json={"email": "new@kjs.test", "password": "password1234"})
    assert r.status_code == 403 and r.json()["code"] == "rejected"


async def test_only_a_pending_sign_up_can_be_rejected(client):
    await make_user(ADMIN, role="admin")
    await make_user("staff@kjs.test")
    await login(client, ADMIN)
    uid = await _id(client, "staff@kjs.test")
    r = await client.post(f"{API}/users/{uid}/reject", headers=HDR, json={"reason": "Changed my mind"})
    assert r.status_code == 409 and r.json()["code"] == "not_pending"


async def test_an_approver_who_is_not_admin_can_reject_but_not_re_approve(client):
    await make_user(ADMIN, role="admin")
    await make_user("approver@kjs.test", permissions=["leads.view", "staff.approve"])
    await _signup(client)
    c = await _as("approver@kjs.test")
    uid = await _id(c, "new@kjs.test")
    r = await c.post(f"{API}/users/{uid}/reject", headers=HDR, json={"reason": "Unknown person"})
    assert r.status_code == 200, r.text
    r = await c.post(f"{API}/users/{uid}/approve", headers=HDR, json={"permissions": []})
    assert r.status_code == 403  # a rejected account is the admin's to approve later
    await c.aclose()


async def test_admin_can_approve_a_rejected_sign_up_later(client):
    await make_user(ADMIN, role="admin")
    await _signup(client)
    await login(client, ADMIN)
    uid = await _id(client, "new@kjs.test")
    await client.post(f"{API}/users/{uid}/reject", headers=HDR, json={"reason": "Wrong branch"})
    r = await client.post(f"{API}/users/{uid}/approve", headers=HDR, json={"permissions": []})
    assert r.status_code == 200 and r.json()["status"] == "active" and r.json()["rejection_reason"] is None
    inbox = (await client.get(f"{API}/approvals", headers=HDR)).json()
    assert inbox["rejected"] == [] and [u["email"] for u in inbox["approved"]] == ["new@kjs.test"]


async def test_employee_without_staff_approve_cannot_reject(client):
    await make_user(ADMIN, role="admin")
    await make_user("staff@kjs.test")
    await _signup(client)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as admin:
        await login(admin, ADMIN)
        uid = await _id(admin, "new@kjs.test")
    c = await _as("staff@kjs.test")
    r = await c.post(f"{API}/users/{uid}/reject", headers=HDR, json={"reason": "Nope nope"})
    assert r.status_code == 403
    await c.aclose()


async def test_enable_cannot_bypass_approve_or_reject(client):
    await make_user(ADMIN, role="admin")
    await _signup(client)
    await login(client, ADMIN)
    uid = await _id(client, "new@kjs.test")
    r = await client.post(f"{API}/users/{uid}/status", headers=HDR, json={"status": "active"})
    assert r.status_code == 409 and r.json()["code"] == "not_approved"


# ---------------------------------------------------------------- permissions
async def test_admin_edits_permissions_and_they_apply_at_once(client):
    await make_user(ADMIN, role="admin")
    await make_user("staff@kjs.test")
    staff = await _as("staff@kjs.test")
    assert (await staff.get(f"{API}/audit", headers=HDR)).status_code == 403
    await login(client, ADMIN)
    uid = await _id(client, "staff@kjs.test")
    r = await client.put(f"{API}/users/{uid}/permissions", headers=HDR, json={"permissions": ["audit.view"]})
    assert r.status_code == 200, r.text
    assert r.json()["permissions"] == ["audit.view", "leads.view"]  # leads.view always stays
    assert (await staff.get(f"{API}/audit", headers=HDR)).status_code == 200  # same session, no re-login
    r = await client.put(f"{API}/users/{uid}/permissions", headers=HDR, json={"permissions": []})
    assert r.json()["permissions"] == ["leads.view"]
    assert (await staff.get(f"{API}/audit", headers=HDR)).status_code == 403
    actions = [a["action"] for a in (await client.get(f"{API}/audit", headers=HDR)).json()]
    assert actions.count("user.permissions_changed") == 2
    await staff.aclose()


async def test_only_an_admin_edits_permissions(client):
    await make_user(ADMIN, role="admin")
    await make_user("approver@kjs.test", permissions=["leads.view", "staff.approve"])
    await make_user("staff@kjs.test")
    c = await _as("approver@kjs.test")
    uid = await _id(c, "staff@kjs.test")
    r = await c.put(f"{API}/users/{uid}/permissions", headers=HDR, json={"permissions": ["audit.view"]})
    assert r.status_code == 403
    await c.aclose()


async def test_permissions_not_for_yourself_admins_unknown_or_pending(client):
    await make_user(ADMIN, role="admin")
    await make_user("admin2@kjs.test", role="admin")
    await make_user("staff@kjs.test")
    await _signup(client)
    await login(client, ADMIN)
    users = {u["email"]: u for u in (await client.get(f"{API}/users", headers=HDR)).json()}
    me = users[ADMIN]["id"]
    r = await client.put(f"{API}/users/{me}/permissions", headers=HDR, json={"permissions": []})
    assert r.status_code == 422 and r.json()["code"] == "self_change"
    pending = users["new@kjs.test"]["id"]
    r = await client.put(f"{API}/users/{pending}/permissions", headers=HDR, json={"permissions": []})
    assert r.status_code == 409 and r.json()["code"] == "not_approved"
    staff = users["staff@kjs.test"]["id"]
    r = await client.put(f"{API}/users/{staff}/permissions", headers=HDR, json={"permissions": ["god.mode"]})
    assert r.status_code == 422 and r.json()["code"] == "unknown_permission"
    other_admin = users["admin2@kjs.test"]["id"]
    r = await client.put(f"{API}/users/{other_admin}/permissions", headers=HDR, json={"permissions": []})
    assert r.status_code == 422 and r.json()["code"] == "admin_has_all"


# ---------------------------------------------------------------- job titles and admin access
async def test_job_titles_are_listed_unique_and_admin_only(client):
    await make_user(ADMIN, role="admin")
    await make_user("approver@kjs.test", permissions=["leads.view", "staff.approve"])
    await login(client, ADMIN)
    assert (await client.post(f"{API}/job-titles", headers=HDR, json={"name": "Sales  Executive"})).json() == {"name": "Sales Executive"}
    assert (await client.post(f"{API}/job-titles", headers=HDR, json={"name": "sales executive"})).json() == {"name": "Sales Executive"}
    await client.post(f"{API}/job-titles", headers=HDR, json={"name": "Accountant"})
    assert (await client.get(f"{API}/job-titles", headers=HDR)).json() == ["Accountant", "Sales Executive"]
    c = await _as("approver@kjs.test")
    assert (await c.post(f"{API}/job-titles", headers=HDR, json={"name": "Boss"})).status_code == 403
    assert (await c.get(f"{API}/job-titles", headers=HDR)).status_code == 200
    await c.aclose()


async def test_user_form_job_title_must_come_from_the_list(client):
    await make_user(ADMIN, role="admin")
    await login(client, ADMIN)
    body = {"name": "Ravi Kumar", "email": "ravi@kjs.test", "phone": "+91 98765 11111", "employee_code": "E1",
            "branch": "Sales", "role": "employee", "job_title": "Wizard"}
    r = await client.post(f"{API}/users", headers=HDR, json=body)
    assert r.status_code == 422 and r.json()["code"] == "unknown_job_title"
    await client.post(f"{API}/job-titles", headers=HDR, json={"name": "Sales Executive"})
    r = await client.post(f"{API}/users", headers=HDR, json=body | {"job_title": "sales executive"})
    assert r.status_code == 201, r.text
    assert r.json()["user"]["job_title"] == "Sales Executive" and r.json()["user"]["role"] == "employee"
    uid = r.json()["user"]["id"]
    r = await client.patch(f"{API}/users/{uid}", headers=HDR, json={"job_title": ""})
    assert r.status_code == 200 and r.json()["job_title"] == ""


async def test_admin_access_only_given_by_an_admin(client):
    await make_user(ADMIN, role="admin")
    await make_user("approver@kjs.test", permissions=["leads.view", "staff.approve"])
    c = await _as("approver@kjs.test")
    body = {"name": "Big Boss", "email": "boss@kjs.test", "phone": "+91 98765 22222", "employee_code": "E2",
            "branch": "HQ", "role": "admin"}
    assert (await c.post(f"{API}/users", headers=HDR, json=body)).status_code == 403
    await c.aclose()


async def test_approved_list_has_real_approvals_only_and_keeps_disabled_ones(client):
    """Accounts an admin created directly were never sign-ups: not in Approved. An approved person who is
    disabled later stays in the list (it is the decision history)."""
    await make_user(ADMIN, role="admin")
    await _signup(client)
    await login(client, ADMIN)
    uid = await _id(client, "new@kjs.test")
    await client.post(f"{API}/users/{uid}/approve", headers=HDR, json={"permissions": []})
    made = await client.post(f"{API}/users", headers=HDR, json={"name": "Made Direct", "email": "direct@kjs.test",
                             "phone": "+91 98765 33333", "employee_code": "D1", "branch": "HQ", "role": "employee"})
    assert made.status_code == 201, made.text
    await client.post(f"{API}/users/{uid}/status", headers=HDR, json={"status": "disabled"})
    approved = (await client.get(f"{API}/approvals", headers=HDR)).json()["approved"]
    assert [u["email"] for u in approved] == ["new@kjs.test"]
    assert approved[0]["status"] == "disabled"
