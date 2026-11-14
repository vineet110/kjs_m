"""Complaints ("Report a problem"): any staff member files one, admins list them, word rules, screenshot access."""
from tests.conftest import HDR, login, make_user

PNG = ("screen.png", b"\x89PNG\r\n\x1a\n..IEND\xaeB`\x82", "image/png")
GOOD = {"kind": "bug", "title": "Import button does nothing",
        "description": "I picked an Excel file with ten rows and pressed Import, but nothing happened "
                       "and no message was shown on the screen.",
        "page_path": "/employee/internal-leads"}


async def _file(client, **change):
    return await client.post("/api/v1/complaints", json=GOOD | change, headers=HDR)


async def test_staff_files_and_admin_sees_it(client):
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    r = await _file(client)
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["kind"] == "bug" and c["page_path"] == "/employee/internal-leads" and c["created_by_name"] == "e"
    assert c["created_at"]  # set by the server, not sent by the browser

    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    rows = (await client.get("/api/v1/complaints")).json()
    assert [x["title"] for x in rows] == ["Import button does nothing"]


async def test_employee_cannot_list(client):
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    assert (await client.get("/api/v1/complaints")).status_code == 403


async def test_must_be_logged_in(client):
    assert (await _file(client)).status_code == 401


async def test_word_rules(client):
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    r = await _file(client, title="Import broken")  # 2 words
    assert r.status_code == 422 and "title" in r.json()["details"]
    r = await _file(client, description="It does not work at all when I press it.")  # 10 words
    assert r.status_code == 422 and "description" in r.json()["details"]
    r = await _file(client, title="   one    two   ")
    assert r.status_code == 422  # spaces are not words


async def test_bad_kind_and_page_refused(client):
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    assert (await _file(client, kind="other")).status_code == 422
    assert (await _file(client, page_path="https://evil.example/x")).status_code == 422  # a path, not a link


async def test_screenshot_only_by_filer_seen_by_admin(client):
    await make_user("e@kjsindia.com")
    await make_user("other@kjsindia.com")
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "e@kjsindia.com")
    cid = (await _file(client)).json()["id"]
    r = await client.post("/api/v1/files", data={"owner_type": "complaint", "owner_id": str(cid)}, files={"file": PNG}, headers=HDR)
    assert r.status_code == 201, r.text
    fid = r.json()["id"]

    await login(client, "other@kjsindia.com")  # another employee: can't add to it or see it
    r = await client.post("/api/v1/files", data={"owner_type": "complaint", "owner_id": str(cid)}, files={"file": PNG}, headers=HDR)
    assert r.status_code == 403
    assert (await client.get(f"/api/v1/files/{fid}/download")).status_code == 403

    await login(client, "admin@kjsindia.com")
    assert (await client.get(f"/api/v1/files/{fid}/download")).status_code == 200
    r = await client.post("/api/v1/files", data={"owner_type": "complaint", "owner_id": str(cid)}, files={"file": PNG}, headers=HDR)
    assert r.status_code == 403  # admins look; only the person who filed it adds a screenshot
    rows = (await client.get("/api/v1/complaints")).json()
    assert [f["name"] for f in rows[0]["files"]] == ["screen.png"]


async def test_screenshot_on_unknown_complaint_refused(client):
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    for owner_id in ("999", "abc", "0"):
        r = await client.post("/api/v1/files", data={"owner_type": "complaint", "owner_id": owner_id}, files={"file": PNG}, headers=HDR)
        assert r.status_code == 403
