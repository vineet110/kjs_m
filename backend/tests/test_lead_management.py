"""Lead Management: contacts (leads grouped per person), Koko / internal lead lists, tasks on a lead,
and the admin User Creation Form (employee code, branch, role, reporting to)."""
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.lead import Lead
from app.models.user import User
from tests.conftest import HDR, login, make_user

ENQ = {"name": "Omar", "email": "omar@alnoor.ae", "consent": True, "phone": "+91 98765 43210", "message": "Need sticks"}
INTERNAL = {"name": "Ravi Traders", "phone": "+91 90000 11111", "company": "Ravi", "message": "Met at the fair"}


async def _uid(email: str) -> int:
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(User.id).where(User.email == email))


async def _web_lead(client, **extra) -> None:
    assert (await client.post("/api/v1/public/leads", json=ENQ | extra, headers=HDR)).status_code == 201


# ---------- Contacts ----------
async def test_contacts_group_by_phone_or_email(client):
    await make_user("a@kjs.in")
    await _web_lead(client)
    await _web_lead(client, phone="+91 95555 00000")  # same email, another phone: same person
    await _web_lead(client, email=None)  # same phone, no email: same person
    await _web_lead(client, name="Sara", phone="+1 98765 43210", email="sara@x.com")  # same last 10 digits, other country
    await login(client, "a@kjs.in")
    rows = (await client.get("/api/v1/employee/contacts")).json()
    assert len(rows) == 2
    omar = next(r for r in rows if r["name"] == "Omar")
    assert (omar["total"], omar["active"], omar["inactive"]) == (3, 3, 0)
    assert omar["email"] == "omar@alnoor.ae"  # taken from an older enquiry when the newest has none
    d = (await client.get(f"/api/v1/employee/contacts/{omar['lead_id']}")).json()
    assert len(d["enquiries"]) == 3  # the contact page agrees with the list


async def test_contacts_closed_count_and_detail(client):
    await make_user("a@kjs.in")
    await _web_lead(client)
    await _web_lead(client)
    await login(client, "a@kjs.in")
    first = (await client.get("/api/v1/employee/leads")).json()[-1]["id"]
    r = await client.patch(f"/api/v1/employee/leads/{first}", json={"status": "closed", "outcome": "spam"}, headers=HDR)
    assert r.status_code == 204
    row = (await client.get("/api/v1/employee/contacts")).json()[0]
    assert (row["active"], row["inactive"], row["total"]) == (1, 1, 2)
    d = (await client.get(f"/api/v1/employee/contacts/{first}")).json()
    assert d["lead"]["id"] == first and len(d["enquiries"]) == 2


async def test_contacts_hide_other_peoples_leads(client):
    await make_user("a@kjs.in")
    await make_user("b@kjs.in")
    await _web_lead(client)
    async with AsyncSessionLocal() as db:  # the lead belongs to b
        lead = await db.scalar(select(Lead))
        lead.assigned_to = await db.scalar(select(User.id).where(User.email == "b@kjs.in"))
        await db.commit()
        lead_id = lead.id
    await login(client, "a@kjs.in")
    assert (await client.get("/api/v1/employee/contacts")).json() == []
    assert (await client.get(f"/api/v1/employee/contacts/{lead_id}")).status_code == 404
    await make_user("boss@kjs.in", role="admin")
    await login(client, "boss@kjs.in")  # leads.view_all sees everyone's
    assert len((await client.get("/api/v1/employee/contacts")).json()) == 1


async def test_contacts_need_login(client):
    # leads.view is an employee default (it can't be taken away), so the forbidden caller is a logged-out one
    assert (await client.get("/api/v1/employee/contacts")).status_code == 401
    assert (await client.get("/api/v1/employee/contacts/1")).status_code == 401


# ---------- Koko and internal leads ----------
async def test_internal_lead_is_mine_and_filterable(client):
    await make_user("a@kjs.in")
    await _web_lead(client)
    await login(client, "a@kjs.in")
    r = await client.post("/api/v1/employee/leads", json=INTERNAL, headers=HDR)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["source"] == "internal" and body["assigned_to"] == await _uid("a@kjs.in")
    assert body["created_by_name"] == "a"
    only = (await client.get("/api/v1/employee/leads?source=internal")).json()
    assert [x["id"] for x in only] == [body["id"]]
    assert (await client.get("/api/v1/employee/leads?source=koko")).json() == []


async def test_internal_lead_checks_input_and_login(client):
    assert (await client.post("/api/v1/employee/leads", json=INTERNAL, headers=HDR)).status_code == 401
    await make_user("a@kjs.in")
    await login(client, "a@kjs.in")
    assert (await client.post("/api/v1/employee/leads", json={"name": "R"}, headers=HDR)).status_code == 422


async def test_admin_lead_list_filters_by_source(client):
    await make_user("boss@kjs.in", role="admin")
    await _web_lead(client)
    await login(client, "boss@kjs.in")
    assert len((await client.get("/api/v1/admin/leads?source=enquiry_form")).json()) == 1
    assert (await client.get("/api/v1/admin/leads?source=koko")).json() == []


# ---------- Tasks on a lead ----------
async def test_lead_tasks(client):
    await make_user("a@kjs.in")
    await login(client, "a@kjs.in")
    lead_id = (await client.post("/api/v1/employee/leads", json=INTERNAL, headers=HDR)).json()["id"]
    r = await client.post(f"/api/v1/employee/leads/{lead_id}/tasks", json={"title": "Send samples"}, headers=HDR)
    assert r.status_code == 201, r.text
    assert r.json()["source_ref"] == f"lead:{lead_id}"
    assert [t["title"] for t in (await client.get(f"/api/v1/employee/leads/{lead_id}/tasks")).json()] == ["Send samples"]
    # It is also in my own task list
    assert any(t["title"] == "Send samples" for t in (await client.get("/api/v1/tasks")).json())


async def test_lead_tasks_forbidden_on_someone_elses_lead(client):
    await make_user("a@kjs.in")
    await make_user("b@kjs.in")
    await login(client, "b@kjs.in")
    lead_id = (await client.post("/api/v1/employee/leads", json=INTERNAL, headers=HDR)).json()["id"]
    await login(client, "a@kjs.in")
    assert (await client.get(f"/api/v1/employee/leads/{lead_id}/tasks")).status_code == 404
    r = await client.post(f"/api/v1/employee/leads/{lead_id}/tasks", json={"title": "Grab it"}, headers=HDR)
    assert r.status_code == 404


# ---------- Files on a lead ----------
async def test_lead_files_upload_list_download(client):
    await make_user("a@kjs.in")
    await login(client, "a@kjs.in")
    lead_id = (await client.post("/api/v1/employee/leads", json=INTERNAL, headers=HDR)).json()["id"]
    for f in [("card.pdf", b"%PDF-1.4 card", "application/pdf"), ("deck.pptx", b"PK deck", "application/octet-stream")]:
        r = await client.post("/api/v1/files", data={"owner_type": "lead", "owner_id": str(lead_id)},
                              files={"file": f}, headers=HDR)
        assert r.status_code == 201, r.text
    files = (await client.get(f"/api/v1/files?owner_type=lead&owner_id={lead_id}")).json()
    assert sorted(x["name"] for x in files) == ["card.pdf", "deck.pptx"]
    d = await client.get(f"/api/v1/files/{files[-1]['id']}/download")
    assert d.status_code == 200 and d.content == b"%PDF-1.4 card"


async def test_lead_files_forbidden_on_someone_elses_lead(client):
    await make_user("a@kjs.in")
    await make_user("b@kjs.in")
    await login(client, "b@kjs.in")
    lead_id = (await client.post("/api/v1/employee/leads", json=INTERNAL, headers=HDR)).json()["id"]
    fid = (await client.post("/api/v1/files", data={"owner_type": "lead", "owner_id": str(lead_id)},
                             files={"file": ("card.pdf", b"%PDF-1.4", "application/pdf")}, headers=HDR)).json()["id"]
    await login(client, "a@kjs.in")
    assert (await client.get(f"/api/v1/files?owner_type=lead&owner_id={lead_id}")).status_code == 403
    assert (await client.get(f"/api/v1/files/{fid}/download")).status_code == 403
    r = await client.post("/api/v1/files", data={"owner_type": "lead", "owner_id": str(lead_id)},
                          files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")}, headers=HDR)
    assert r.status_code == 403
    # a made-up lead id is refused the same way
    r = await client.post("/api/v1/files", data={"owner_type": "lead", "owner_id": "abc"},
                          files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")}, headers=HDR)
    assert r.status_code == 403


async def test_lead_files_still_block_risky_types(client):
    await make_user("a@kjs.in")
    await login(client, "a@kjs.in")
    lead_id = (await client.post("/api/v1/employee/leads", json=INTERNAL, headers=HDR)).json()["id"]
    for name in ["run.exe", "page.html", "logo.svg"]:
        r = await client.post("/api/v1/files", data={"owner_type": "lead", "owner_id": str(lead_id)},
                              files={"file": (name, b"x", "application/octet-stream")}, headers=HDR)
        assert r.status_code == 422 and r.json()["code"] == "file_type"


# ---------- User Creation Form ----------
async def _form(boss_id: int, **extra) -> dict:
    return {"name": "Neha", "email": "neha@kjs.in", "phone": "+91 98480 12345", "employee_code": "KJS-014",
            "branch": "Main Branch", "role": "employee", "reporting_to": boss_id} | extra


async def test_admin_creates_user_who_can_log_in(client):
    await make_user("boss@kjs.in", role="admin")
    await login(client, "boss@kjs.in")
    r = await client.post("/api/v1/admin/users", json=await _form(await _uid("boss@kjs.in")), headers=HDR)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user"]["employee_code"] == "KJS-014" and body["user"]["status"] == "active"
    await client.post("/api/v1/auth/logout", headers=HDR)
    await login(client, "neha@kjs.in", body["temp_password"])
    p = (await client.get("/api/v1/auth/profile")).json()
    assert (p["branch"], p["employee_code"], p["reporting_to_name"]) == ("Main Branch", "KJS-014", "Admin")


async def test_create_user_rules(client):
    await make_user("boss@kjs.in", role="admin")
    await login(client, "boss@kjs.in")
    boss = await _uid("boss@kjs.in")
    assert (await client.post("/api/v1/admin/users", json=await _form(boss), headers=HDR)).status_code == 201
    assert (await client.post("/api/v1/admin/users", json=await _form(boss), headers=HDR)).status_code == 409
    bad = await _form(9999, email="z@kjs.in")
    assert (await client.post("/api/v1/admin/users", json=bad, headers=HDR)).status_code == 422
    # "Reporting to" may be empty: the top of the chain reports to no one, and can still be edited
    top = await _form(None, email="top@kjs.in")
    assert (await client.post("/api/v1/admin/users", json=top, headers=HDR)).status_code == 201
    edit = {k: v for k, v in top.items() if k != "email"} | {"branch": "HQ"}
    r = await client.patch(f"/api/v1/admin/users/{await _uid('top@kjs.in')}", json=edit, headers=HDR)
    assert r.status_code == 200, r.text


async def test_staff_cannot_create_users(client):
    await make_user("boss@kjs.in", role="admin")
    await make_user("a@kjs.in")
    await login(client, "a@kjs.in")
    r = await client.post("/api/v1/admin/users", json=await _form(await _uid("boss@kjs.in")), headers=HDR)
    assert r.status_code == 403


async def test_approver_cannot_make_admins_or_edit(client):
    await make_user("boss@kjs.in", role="admin")
    await make_user("hr@kjs.in", permissions=["leads.view", "staff.approve"])
    await make_user("a@kjs.in")
    await login(client, "hr@kjs.in")
    boss = await _uid("boss@kjs.in")
    r = await client.post("/api/v1/admin/users", json=await _form(boss, role="admin"), headers=HDR)
    assert r.status_code == 403
    edit = {k: v for k, v in (await _form(boss)).items() if k != "email"}
    assert (await client.patch(f"/api/v1/admin/users/{await _uid('a@kjs.in')}", json=edit, headers=HDR)).status_code == 403


async def test_admin_edits_role_and_branch(client):
    await make_user("boss@kjs.in", role="admin")
    await make_user("a@kjs.in")
    await login(client, "boss@kjs.in")
    edit = {k: v for k, v in (await _form(await _uid("boss@kjs.in"), branch="Pashamylaram")).items() if k != "email"}
    r = await client.patch(f"/api/v1/admin/users/{await _uid('a@kjs.in')}", json=edit, headers=HDR)
    assert r.status_code == 200, r.text
    assert (r.json()["branch"], r.json()["name"]) == ("Pashamylaram", "Neha")
    # Nobody reports to themselves
    loop = edit | {"reporting_to": await _uid("a@kjs.in")}
    assert (await client.patch(f"/api/v1/admin/users/{await _uid('a@kjs.in')}", json=loop, headers=HDR)).status_code == 422


async def test_no_reporting_loops(client):
    # A reports to B; then making B report to A must be refused (and a longer A -> B -> C -> A too)
    await make_user("boss@kjs.in", role="admin")
    for e in ("a@kjs.in", "b@kjs.in", "c@kjs.in"):
        await make_user(e)
    await login(client, "boss@kjs.in")
    a, b, c = [await _uid(e) for e in ("a@kjs.in", "b@kjs.in", "c@kjs.in")]
    edit = {k: v for k, v in (await _form(b)).items() if k != "email"}

    async def set_boss(who: int, boss: int) -> int:
        return (await client.patch(f"/api/v1/admin/users/{who}", json=edit | {"reporting_to": boss}, headers=HDR)).status_code

    assert await set_boss(a, b) == 200
    assert await set_boss(b, a) == 422
    assert await set_boss(b, c) == 200
    assert await set_boss(c, a) == 422


PNG = ("me.png", b"\x89PNG\r\n\x1a\n" + b"0" * 32, "image/png")


async def _photo(client, owner_id) -> int:
    r = await client.post("/api/v1/files", data={"owner_type": "user", "owner_id": str(owner_id)},
                          files={"file": PNG}, headers=HDR)
    return r.status_code


async def test_photo_rules(client):
    await make_user("boss@kjs.in", role="admin")
    await make_user("hr@kjs.in", permissions=["leads.view", "staff.approve"])
    await make_user("a@kjs.in")
    # A staff member: own photo only
    await login(client, "a@kjs.in")
    assert await _photo(client, await _uid("hr@kjs.in")) == 403
    await client.post("/api/v1/auth/logout", headers=HDR)
    # An approver: not the admin's photo, not a user who doesn't exist, but yes a staff member's
    await login(client, "hr@kjs.in")
    assert await _photo(client, await _uid("boss@kjs.in")) == 403
    assert await _photo(client, 99999) == 403
    assert await _photo(client, "abc") == 403
    assert await _photo(client, await _uid("a@kjs.in")) == 201


async def test_editing_one_field_of_an_account_leaves_the_rest(client):
    """Only the fields sent change: two admins editing different fields don't undo each other."""
    await make_user("boss@kjs.in", role="admin")
    await make_user("a@kjs.in")
    await login(client, "boss@kjs.in")
    a = await _uid("a@kjs.in")
    full = {k: v for k, v in (await _form(await _uid("boss@kjs.in"), branch="Pashamylaram")).items() if k != "email"}
    assert (await client.patch(f"/api/v1/admin/users/{a}", json=full, headers=HDR)).status_code == 200
    r = await client.patch(f"/api/v1/admin/users/{a}", json={"branch": "Hyderabad"}, headers=HDR)
    assert r.status_code == 200, r.text
    assert (r.json()["branch"], r.json()["name"]) == ("Hyderabad", full["name"])
    r = await client.patch(f"/api/v1/admin/users/{a}", json={"reporting_to": a}, headers=HDR)
    assert r.status_code == 422  # the whole account is still checked (nobody reports to themselves)
