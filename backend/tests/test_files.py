"""Files: upload rules, owner access, download, public files, delete needs approval."""
from tests.conftest import HDR, login, make_user

PDF = ("spec.pdf", b"%PDF-1.4 test", "application/pdf")


async def _upload(client, owner_id="coffee-stick", file=PDF, public=False):
    return await client.post("/api/v1/files", data={"owner_type": "product", "owner_id": owner_id, "is_public": str(public).lower()},
                             files={"file": file}, headers=HDR)


async def test_upload_list_download(client):
    await make_user("cat@kjsindia.com", permissions=["leads.view", "catalog.edit"])
    await login(client, "cat@kjsindia.com")
    r = await _upload(client)
    assert r.status_code == 201, r.text
    fid = r.json()["id"]
    assert [f["name"] for f in (await client.get("/api/v1/files?owner_type=product&owner_id=coffee-stick")).json()] == ["spec.pdf"]
    d = await client.get(f"/api/v1/files/{fid}/download")
    assert d.status_code == 200 and d.content == b"%PDF-1.4 test" and "attachment" in d.headers["content-disposition"]


async def test_upload_needs_owner_permission(client):
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    assert (await _upload(client)).status_code == 403


async def test_bad_type_and_unknown_owner_rejected(client):
    await make_user("cat@kjsindia.com", permissions=["leads.view", "catalog.edit"])
    await login(client, "cat@kjsindia.com")
    r = await _upload(client, file=("run.exe", b"MZ", "application/octet-stream"))
    assert r.status_code == 422 and r.json()["code"] == "file_type"
    r = await client.post("/api/v1/files", data={"owner_type": "nope", "owner_id": "1"}, files={"file": PDF}, headers=HDR)
    assert r.status_code == 403


async def test_public_files_only_when_marked_public(client):
    await make_user("cat@kjsindia.com", permissions=["leads.view", "catalog.edit"])
    await login(client, "cat@kjsindia.com")
    private_id = (await _upload(client)).json()["id"]
    public_id = (await _upload(client, file=("photo.png", b"\x89PNG..", "image/png"), public=True)).json()["id"]
    client.cookies.clear()
    assert (await client.get(f"/api/v1/public/files/{private_id}")).status_code == 404
    r = await client.get(f"/api/v1/public/files/{public_id}")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"


async def test_delete_needs_approval(client):
    await make_user("cat@kjsindia.com", permissions=["leads.view", "catalog.edit"])
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "cat@kjsindia.com")
    fid = (await _upload(client)).json()["id"]
    r = await client.post(f"/api/v1/files/{fid}/delete-request", json={"reason": "Old version"}, headers=HDR)
    assert r.json()["delete_status"] == "requested"
    assert (await client.post(f"/api/v1/files/{fid}/delete-decision", json={"approve": True}, headers=HDR)).status_code == 403
    assert (await client.get(f"/api/v1/files/{fid}/download")).status_code == 200  # still there

    await login(client, "admin@kjsindia.com")
    assert [f["id"] for f in (await client.get("/api/v1/files/delete-requests")).json()] == [fid]
    r = await client.post(f"/api/v1/files/{fid}/delete-decision", json={"approve": True}, headers=HDR)
    assert r.json()["delete_status"] == "approved"
    assert (await client.get(f"/api/v1/files/{fid}/download")).status_code == 404


async def test_approvals_inbox_sections_follow_permissions(client):
    await make_user("e@kjsindia.com")
    await make_user("new@kjsindia.com", status="pending")
    await login(client, "e@kjsindia.com")
    assert (await client.get("/api/v1/admin/approvals")).json() == {"signups": None, "regularizations": None, "file_deletes": None}
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    inbox = (await client.get("/api/v1/admin/approvals")).json()
    assert [u["email"] for u in inbox["signups"]] == ["new@kjsindia.com"]
    assert inbox["regularizations"] == [] and inbox["file_deletes"] == []
