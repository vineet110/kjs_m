"""CR22: a public spec sheet (PDF) opens in the visitor's browser, with local storage as well as R2.
Chrome's PDF viewer shows nothing for a PDF sent with "Content-Security-Policy: sandbox", so a real PDF goes
without it (as the staff preview does); pictures and everything else stay sandboxed."""
from tests.conftest import HDR, login, make_user, real_png
from tests.test_files import PDF, _upload

PNG = ("photo.png", real_png(), "image/png")  # a real picture: uploads are checked (#135)


async def _public(client, file) -> int:
    await make_user("cat@kjsindia.com", permissions=["leads.view", "catalog.edit"])
    await login(client, "cat@kjsindia.com")
    p = (await client.post("/api/v1/admin/products", json={"category_slug": "coffee", "name": "Spec Coffee"}, headers=HDR)).json()
    r = await _upload(client, owner_id=p["slug"], file=file, public=True)
    assert r.status_code == 201, r.text
    client.cookies.clear()
    return r.json()["id"]


async def test_a_public_pdf_opens_in_the_browser(client):
    r = await client.get(f"/api/v1/public/files/{await _public(client, PDF)}")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"].startswith("inline")
    assert "sandbox" not in r.headers["content-security-policy"]  # Chrome would show an empty page
    assert r.headers["content-security-policy"] == "frame-ancestors 'self'"
    assert r.headers["x-content-type-options"] == "nosniff"


async def test_a_public_picture_stays_sandboxed(client):
    r = await client.get(f"/api/v1/public/files/{await _public(client, PNG)}")
    assert r.status_code == 200 and r.headers["content-security-policy"] == "sandbox"


async def test_on_r2_the_public_pdf_link_opens_inline_and_staff_downloads_stay_attachments(client, monkeypatch):
    from app.core.storage import storage
    seen = []
    monkeypatch.setattr(type(storage()), "url", lambda self, key, filename="", inline=False: seen.append(inline) or "https://r2.example/x")
    fid = await _public(client, PDF)
    r = await client.get(f"/api/v1/public/files/{fid}")
    assert r.status_code == 302 and r.headers["location"] == "https://r2.example/x"
    await login(client, "cat@kjsindia.com")
    assert (await client.get(f"/api/v1/files/{fid}/download")).status_code == 302
    assert seen == [True, False]
