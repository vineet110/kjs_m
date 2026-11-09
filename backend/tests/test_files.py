"""Files: upload rules, owner access, download, public files, delete needs approval."""
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.catalog import Category, Product
from tests.conftest import HDR, login, make_user

PDF = ("spec.pdf", b"%PDF-1.4 test", "application/pdf")


async def _product(slug: str) -> None:
    """Files can only be added to a product that exists."""
    async with AsyncSessionLocal() as db:
        if not await db.scalar(select(Product.id).where(Product.slug == slug)):
            cat = await db.scalar(select(Category.id).where(Category.slug == "coffee"))
            db.add(Product(category_id=cat, slug=slug, name=slug))
            await db.commit()


async def _upload(client, owner_id="coffee-stick", file=PDF, public=False):
    await _product(owner_id)
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
    p = (await client.post("/api/v1/admin/products", json={"category_slug": "coffee", "name": "Stick Coffee"}, headers=HDR)).json()
    private_id = (await _upload(client, owner_id=p["slug"])).json()["id"]
    public_id = (await _upload(client, owner_id=p["slug"], file=("photo.png", b"\x89PNG..", "image/png"), public=True)).json()["id"]
    client.cookies.clear()
    assert (await client.get(f"/api/v1/public/files/{private_id}")).status_code == 404
    r = await client.get(f"/api/v1/public/files/{public_id}")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.headers["content-security-policy"] == "sandbox"
    assert [f["id"] for f in (await client.get(f"/api/v1/public/products/{p['slug']}/files")).json()] == [public_id]

    # Hiding the product takes its files off the website too
    await login(client, "cat@kjsindia.com")
    await client.patch(f"/api/v1/admin/products/{p['id']}", json={"category_slug": "coffee", "name": "Stick Coffee",
                                                                 "is_active": False}, headers=HDR)
    client.cookies.clear()
    assert (await client.get(f"/api/v1/public/files/{public_id}")).status_code == 404
    assert (await client.get(f"/api/v1/public/products/{p['slug']}/files")).json() == []


async def test_nobody_approves_their_own_delete(client):
    await make_user("cat@kjsindia.com", permissions=["leads.view", "catalog.edit", "files.approve"])
    await login(client, "cat@kjsindia.com")
    fid = (await _upload(client)).json()["id"]
    await client.post(f"/api/v1/files/{fid}/delete-request", json={"reason": "Old version"}, headers=HDR)
    r = await client.post(f"/api/v1/files/{fid}/delete-decision", json={"approve": True}, headers=HDR)
    assert r.status_code == 403 and r.json()["code"] == "own_request"


async def test_seeing_a_file_is_not_enough_to_request_its_delete(client):
    await make_user("cat@kjsindia.com", permissions=["leads.view", "catalog.edit"])
    await make_user("e@kjsindia.com")  # can read product files, can't edit products
    await login(client, "cat@kjsindia.com")
    fid = (await _upload(client)).json()["id"]
    await login(client, "e@kjsindia.com")
    r = await client.post(f"/api/v1/files/{fid}/delete-request", json={"reason": "I want it gone"}, headers=HDR)
    assert r.status_code == 403


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


async def test_view_shows_the_file_in_the_page_to_allowed_staff_only(client):
    """In-page preview (order boards PR 2): inline, never cached, nosniff; sandboxed except PDFs."""
    await make_user("cat@kjsindia.com", permissions=["leads.view", "catalog.edit"])
    await make_user("e@kjsindia.com")
    await login(client, "cat@kjsindia.com")
    pdf = (await _upload(client)).json()["id"]
    csv = (await _upload(client, file=("prices.csv", b"item,qty\nA,1\n", "text/csv"))).json()["id"]

    r = await client.get(f"/api/v1/files/{pdf}/view")
    assert r.status_code == 200 and r.content == b"%PDF-1.4 test"
    assert r.headers["content-type"] == "application/pdf" and r.headers["content-disposition"] == "inline"
    assert r.headers["cache-control"] == "private, no-store" and r.headers["x-content-type-options"] == "nosniff"
    # Chrome's PDF viewer won't open a sandboxed PDF: a real PDF may only be framed by our own pages
    assert r.headers["content-security-policy"] == "frame-ancestors 'self'"
    fake = (await _upload(client, file=("trick.pdf", b"<html><script>x</script>", "application/pdf"))).json()["id"]
    assert (await client.get(f"/api/v1/files/{fake}/view")).headers["content-security-policy"] == "sandbox"
    r = await client.get(f"/api/v1/files/{csv}/view")
    assert r.status_code == 200 and r.content == b"item,qty\nA,1\n"
    assert r.headers["content-security-policy"] == "sandbox" and r.headers["content-type"].startswith("text/csv")

    client.cookies.clear()
    assert (await client.get(f"/api/v1/files/{pdf}/view")).status_code == 401


async def test_view_of_a_board_file_only_for_people_on_the_board(client):
    from tests.test_boards import _ids, board_body
    await make_user("boss@kjsindia.com", permissions=["leads.view", "boards.manage"])
    await make_user("pack@kjsindia.com")
    await make_user("other@kjsindia.com")
    pack, = await _ids("pack@kjsindia.com")
    await login(client, "boss@kjsindia.com")
    assert (await client.post("/api/v1/boards", json=board_body(pack, pack), headers=HDR)).status_code == 201
    fid = (await client.post("/api/v1/files", data={"owner_type": "board", "owner_id": "ABC117-3"},
                             files={"file": ("po.pdf", b"%PDF", "application/pdf")}, headers=HDR)).json()["id"]
    await login(client, "pack@kjsindia.com")
    assert (await client.get(f"/api/v1/files/{fid}/view")).status_code == 200
    await login(client, "other@kjsindia.com")
    assert (await client.get(f"/api/v1/files/{fid}/view")).status_code == 403
