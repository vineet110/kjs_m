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


# ---------- Edge cases (review of go-live PR 3) ----------

async def test_holiday_name_edges(client):
    """Spaces only, a number, 101 letters are refused; 100 letters with spaces around, and a Hindi name, are
    saved (trimmed); an old one-letter holiday saved before the rule is still listed."""
    from datetime import date

    from app.models.calendar import Holiday
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    url = "/api/v1/admin/holidays"
    for bad in ["   ", "", 7, None, "x" * 101]:
        r = await client.post(url, json={"day": "2027-03-01", "name": bad}, headers=HDR)
        assert r.status_code == 422, bad
    assert (await client.post(url, json={"day": "2027-03-02", "name": "  " + "x" * 100 + "  "}, headers=HDR)).status_code == 201
    r = await client.post(url, json={"day": "2027-03-03", "name": "होली"}, headers=HDR)
    assert r.status_code == 201 and r.json()["name"] == "होली"
    async with AsyncSessionLocal() as db:
        db.add(Holiday(day=date(2027, 3, 4), name="a"))
        await db.commit()
    r = await client.get(f"{url}?year=2027")
    assert r.status_code == 200
    names = [h["name"] for h in r.json()]
    assert "a" in names and "x" * 100 in names


async def test_attendance_export_one_day_and_reversed(client):
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    assert (await client.get("/api/v1/attendance/export?start_date=2026-01-01&end_date=2026-01-01")).status_code == 200
    r = await client.get("/api/v1/attendance/export?start_date=2026-01-02&end_date=2026-01-01")
    assert r.status_code == 422 and r.json()["code"] == "bad_dates"


async def test_profile_photo_extension_case_and_no_extension(client):
    """.PNG (capital letters, as some phones name them) is a picture too; a PDF or a name with no extension is not."""
    from tests.test_files import PNG
    await make_user("a@kjsindia.com")
    await login(client, "a@kjsindia.com")
    me = await _uid("a@kjsindia.com")
    for name, ok in [("ME.PNG", True), ("me.pdf", False), ("me", False)]:
        body = PNG[1] if ok else b"%PDF-1.4 %%EOF"
        r = await client.post("/api/v1/files", data={"owner_type": "user", "owner_id": str(me)},
                              files={"file": (name, body, "image/png")}, headers=HDR)
        assert (r.status_code == 201) == ok, (name, r.status_code, r.text)
        if not ok:
            assert r.json()["code"] == "file_type" and r.json()["details"]["allowed"] == ["jpeg", "jpg", "png", "webp"]


async def test_a_file_you_may_not_see_looks_missing_everywhere(client):
    """download, view and delete-request: the same 404 answer as an id that was never used (TC-FILE-11)."""
    from tests.test_complaints import GOOD, PNG
    await make_user("e@kjsindia.com")
    await make_user("other@kjsindia.com")
    await login(client, "e@kjsindia.com")  # a complaint's screenshot: only the filer and admins see it
    cid = (await client.post("/api/v1/complaints", json=GOOD, headers=HDR)).json()["id"]
    r = await client.post("/api/v1/files", data={"owner_type": "complaint", "owner_id": str(cid)}, files={"file": PNG}, headers=HDR)
    assert r.status_code == 201, r.text
    fid = r.json()["id"]
    await login(client, "other@kjsindia.com")
    for path, method in [("download", "get"), ("view", "get"), ("delete-request", "post")]:
        kw = {"json": {"reason": "not mine to see"}, "headers": HDR} if method == "post" else {}
        hidden = await getattr(client, method)(f"/api/v1/files/{fid}/{path}", **kw)
        missing = await getattr(client, method)(f"/api/v1/files/99999999/{path}", **kw)
        assert hidden.status_code == missing.status_code == 404, (path, hidden.status_code, hidden.text)
        assert (hidden.json()["code"], hidden.json()["message"]) == (missing.json()["code"], missing.json()["message"])


async def test_closing_a_lead_trims_the_outcome_and_reopening_needs_none(client):
    await make_user("e@kjsindia.com", permissions=["leads.view"])
    assert (await client.post("/api/v1/public/leads", json={
        "name": "Omar", "email": "omar@alnoor.ae", "consent": True, "phone": "+91 98765 43210"})).status_code == 201
    await login(client, "e@kjsindia.com")
    async with AsyncSessionLocal() as db:
        lead_id = await db.scalar(select(Lead.id))
    url = f"/api/v1/employee/leads/{lead_id}"
    assert (await client.patch(url, json={"status": "closed"}, headers=HDR)).json()["code"] == "outcome_required"
    assert (await client.patch(url, json={"status": "closed", "outcome": " \t"}, headers=HDR)).status_code == 422
    assert (await client.patch(url, json={"status": "closed", "outcome": "x" * 41}, headers=HDR)).status_code == 422
    assert (await client.patch(url, json={"status": "closed", "outcome": "  won "}, headers=HDR)).status_code == 204
    async with AsyncSessionLocal() as db:
        assert (await db.get(Lead, lead_id)).outcome == "won"
    assert (await client.patch(url, json={"status": "contacted"}, headers=HDR)).status_code == 204


async def test_sla_breach_links_each_person_to_a_page_they_can_open(client, monkeypatch):
    """Managers get All Enquiries; an owner without leads.view_all gets their own lead page; a manager who owns
    the lead gets one notice for it, not two."""
    from app.core.config import ini
    from app.models.notification import Notification
    from app.services import lead_service
    from tests.test_leads_sla import ist
    monkeypatch.setenv("KJS__SLA__RESPOND_MINUTES", "20")
    monkeypatch.setenv("KJS__SLA__ESCALATE_AFTER_MINUTES", "10")
    ini.reload_now()
    try:
        await make_user("admin@kjsindia.com", role="admin")
        await make_user("e@kjsindia.com", permissions=["leads.view"])
        for _ in range(2):
            assert (await client.post("/api/v1/public/leads", json={
                "name": "Omar", "email": "omar@alnoor.ae", "consent": True, "phone": "+91 98765 43210"})).status_code == 201
        admin, e = await _uid("admin@kjsindia.com"), await _uid("e@kjsindia.com")
        async with AsyncSessionLocal() as db:
            first, second = (await db.scalars(select(Lead).order_by(Lead.id))).all()
            first.assigned_to, second.assigned_to = e, admin
            first.created_at = second.created_at = ist("2026-10-26", "10:00")
            await db.commit()
            first_id = first.id
            await lead_service.sla_check(db, now=ist("2026-10-26", "10:45"))
            await db.commit()
            rows = (await db.scalars(select(Notification).where(Notification.kind == "lead.sla_breach"))).all()
        got = sorted((n.user_id, n.link) for n in rows)
        assert got == sorted([(admin, "/admin/leads"), (admin, "/admin/leads"), (e, f"/employee/contacts/{first_id}")])
    finally:
        monkeypatch.undo()
        ini.reload_now()


async def test_step_done_links_a_creator_without_boards_manage_to_the_employee_page(client):
    from app.models.notification import Notification
    from tests.test_board_people import B, _create_as_plain_owner, _team
    ids = await _team()
    await make_user("manager@kjsindia.com", permissions=["boards.manage"])
    b = await _create_as_plain_owner(client, ids)
    await login(client, "blend@kjsindia.com")
    assert (await client.post(f"{B}/steps/{b['steps'][0]['id']}/done", headers=HDR)).status_code == 200
    async with AsyncSessionLocal() as db:
        rows = (await db.scalars(select(Notification).where(Notification.kind == "board.step_done"))).all()
    links = {n.user_id: n.link for n in rows}
    assert links[ids["owner"]] == "/employee/order-boards/ABC117-3"
    assert links[await _uid("manager@kjsindia.com")] == "/admin/order-boards/ABC117-3"
    assert ids["blend"] not in links  # not told about their own step
