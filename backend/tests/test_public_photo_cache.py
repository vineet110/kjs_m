"""R44 edge cases: which public files the API sends itself (small web photos) and which keep the R2 link,
and what a visitor gets when R2 has a bad moment or the product is hidden."""
import pytest

from app.core.storage import StorageError, storage
from app.services import file_service
from tests.conftest import HDR, login, make_user
from tests.test_files import PDF, PNG, _upload

def _webp() -> tuple[str, bytes, str]:
    import io

    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (8, 8), "green").save(b, "WEBP")
    return ("photo.webp", b.getvalue(), "image/webp")


@pytest.fixture
def like_r2(monkeypatch):
    """Storage that behaves like R2: links for downloads, no file on disk, bytes from get()."""
    store = type(storage())
    monkeypatch.setattr(store, "url", lambda self, key, filename="", inline=False: "https://r2.example/signed")
    monkeypatch.delattr(store, "file_path")
    return store


async def _product(client, name="Edge Coffee") -> str:
    await make_user("cat@kjsindia.com", permissions=["leads.view", "catalog.edit"])
    await login(client, "cat@kjsindia.com")
    return (await client.post("/api/v1/admin/products", json={"category_slug": "coffee", "name": name}, headers=HDR)).json()["slug"]


async def test_a_photo_over_the_limit_keeps_the_r2_link(client, like_r2, monkeypatch):
    slug = await _product(client)
    fid = (await _upload(client, owner_id=slug, file=PNG, public=True)).json()["id"]
    monkeypatch.setattr(file_service, "PUBLIC_PHOTO_MAX", len(PNG[1]) - 1)  # one byte too big
    client.cookies.clear()
    r = await client.get(f"/api/v1/public/files/{fid}")
    assert r.status_code == 302 and r.headers["location"] == "https://r2.example/signed"
    monkeypatch.setattr(file_service, "PUBLIC_PHOTO_MAX", len(PNG[1]))  # exactly at the limit: sent by us
    assert (await client.get(f"/api/v1/public/files/{fid}")).status_code == 200


async def test_staff_downloads_of_a_public_photo_still_use_the_link(client, like_r2):
    """Staff get the photo as an attachment from R2, never the cached public copy."""
    slug = await _product(client)
    fid = (await _upload(client, owner_id=slug, file=PNG, public=True)).json()["id"]
    r = await client.get(f"/api/v1/files/{fid}/download")
    assert r.status_code == 302


async def test_a_pdf_never_comes_through_the_api_on_r2(client, like_r2):
    slug = await _product(client)
    fid = (await _upload(client, owner_id=slug, file=PDF, public=True)).json()["id"]
    client.cookies.clear()
    assert (await client.get(f"/api/v1/public/files/{fid}")).status_code == 302


async def test_r2_having_a_bad_moment_is_not_cached(client, like_r2, monkeypatch):
    slug = await _product(client)
    fid = (await _upload(client, owner_id=slug, file=PNG, public=True)).json()["id"]

    def down(self, key):
        raise StorageError("timeout")
    monkeypatch.setattr(like_r2, "get", down)
    client.cookies.clear()
    r = await client.get(f"/api/v1/public/files/{fid}")
    assert r.status_code >= 400
    assert "max-age" not in r.headers.get("cache-control", "")  # nobody may keep the failure for 10 minutes


async def test_a_hidden_products_photo_is_gone_from_the_api(client, like_r2):
    slug = await _product(client)
    fid = (await _upload(client, owner_id=slug, file=PNG, public=True)).json()["id"]
    pid = (await client.get(f"/api/v1/public/products/{slug}")).json()["id"]
    assert (await client.patch(f"/api/v1/admin/products/{pid}", json={"is_active": False}, headers=HDR)).status_code == 200
    client.cookies.clear()
    assert (await client.get(f"/api/v1/public/files/{fid}")).status_code == 404


async def test_a_webp_photo_is_sent_with_its_type(client, like_r2):
    slug = await _product(client)
    r = await _upload(client, owner_id=slug, file=_webp(), public=True)
    assert r.status_code == 201, r.text
    client.cookies.clear()
    got = await client.get(f"/api/v1/public/files/{r.json()['id']}")
    assert got.status_code == 200 and got.headers["content-type"] == "image/webp"
    assert got.headers["x-content-type-options"] == "nosniff" and got.headers["content-security-policy"] == "sandbox"
