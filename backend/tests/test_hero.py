"""Home page hero (Admin > Website > Hero): slides, stats, pictures (shrunk on upload), limits, permissions."""
import io

from PIL import Image

from tests.conftest import HDR, login, make_user


async def _editor(client):
    await make_user("web@kjsindia.com", permissions=["leads.view", "content.edit"])
    await login(client, "web@kjsindia.com")


def _jpeg(w: int, h: int) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (w, h), (200, 150, 60)).save(b, "JPEG", quality=95)
    return b.getvalue()


async def _upload(client, data: bytes, name: str = "pack.jpg"):
    return await client.post("/api/v1/files", data={"owner_type": "website", "owner_id": "hero", "is_public": "true"},
                             files={"file": (name, data, "image/jpeg")}, headers=HDR)


async def test_public_hero_is_empty_until_admin_adds_slides(client):
    # Empty lists: the home page keeps its built-in slides and live counts
    assert (await client.get("/api/v1/public/hero")).json() == {"slides": [], "stats": []}


async def test_editor_adds_slide_with_pictures_and_it_is_public(client):
    await _editor(client)
    up = await _upload(client, _jpeg(3000, 2000))
    assert up.status_code == 201, up.text
    fid = up.json()["id"]
    r = await client.post("/api/v1/content/hero/slides", json={
        "eyebrow": "Private label", "title": "Your brand, our factory", "text": "Launch faster.",
        "cta_text": "Start now", "cta_link": "/private-label", "tone": "rose", "image_ids": [fid]}, headers=HDR)
    assert r.status_code == 201, r.text
    await client.post("/api/v1/content/hero/slides", json={"title": "Paused slide", "is_active": False}, headers=HDR)
    slides = (await client.get("/api/v1/public/hero")).json()["slides"]
    assert [s["title"] for s in slides] == ["Your brand, our factory"]  # only active ones
    assert slides[0]["images"] == [f"/api/v1/public/files/{fid}"] and slides[0]["tone"] == "rose"
    # The picture is public (no login) and was shrunk to image_max_px (1600) on its longest side
    client.cookies.clear()
    pic = await client.get(f"/api/v1/public/files/{fid}")
    assert pic.status_code == 200
    assert max(Image.open(io.BytesIO(pic.content)).size) == 1600


async def test_slide_checks_tone_pictures_and_link(client):
    await _editor(client)
    assert (await client.post("/api/v1/content/hero/slides", json={"title": "Bad tone", "tone": "neon"}, headers=HDR)).status_code == 422
    # A picture id that is not a hero picture (here: does not exist) is refused
    assert (await client.post("/api/v1/content/hero/slides", json={"title": "Bad pic", "image_ids": [999]}, headers=HDR)).status_code == 422
    assert (await client.post("/api/v1/content/hero/slides", json={"title": "Too many", "image_ids": [1, 2, 3, 4]}, headers=HDR)).status_code == 422
    assert (await client.post("/api/v1/content/hero/slides", json={"title": "Bad link", "cta_link": "javascript:alert(1)"}, headers=HDR)).status_code == 422


async def test_only_pictures_can_be_uploaded_for_the_hero(client):
    await _editor(client)
    r = await client.post("/api/v1/files", data={"owner_type": "website", "owner_id": "hero", "is_public": "true"},
                          files={"file": ("sheet.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")}, headers=HDR)
    assert r.status_code == 422
    assert (await _upload(client, b"not really a jpeg")).status_code == 422


async def test_slide_and_stat_limits_from_site_ui_ini(client, monkeypatch):
    from app.core.config import ini
    monkeypatch.setenv("KJS__SITE_UI__HERO_MAX_SLIDES", "1")
    monkeypatch.setenv("KJS__SITE_UI__HERO_MAX_STATS", "1")
    ini.reload_now()
    await _editor(client)
    assert (await client.post("/api/v1/content/hero/slides", json={"title": "First"}, headers=HDR)).status_code == 201
    assert (await client.post("/api/v1/content/hero/slides", json={"title": "Second"}, headers=HDR)).status_code == 422
    # A switched-off slide can still be saved (ready for later)
    assert (await client.post("/api/v1/content/hero/slides", json={"title": "Later", "is_active": False}, headers=HDR)).status_code == 201
    assert (await client.post("/api/v1/content/hero/stats", json={"number": "24", "label": "items to choose from"}, headers=HDR)).status_code == 201
    assert (await client.post("/api/v1/content/hero/stats", json={"number": "5", "label": "product families"}, headers=HDR)).status_code == 422


async def test_editing_a_slide_changes_only_what_was_sent(client):
    await _editor(client)
    s = (await client.post("/api/v1/content/hero/slides", json={"title": "Coffee for your brand", "text": "Kept"}, headers=HDR)).json()
    r = await client.patch(f"/api/v1/content/hero/slides/{s['id']}", json={"is_active": False}, headers=HDR)
    assert r.status_code == 200 and r.json()["text"] == "Kept" and r.json()["is_active"] is False
    assert (await client.patch(f"/api/v1/content/hero/slides/{s['id']}", json={"title": None}, headers=HDR)).status_code == 422
    assert (await client.delete(f"/api/v1/content/hero/slides/{s['id']}", headers=HDR)).status_code == 204
    assert (await client.get("/api/v1/content/hero")).json()["slides"] == []


async def test_stats_are_public_in_order(client):
    await _editor(client)
    await client.post("/api/v1/content/hero/stats", json={"number": "0.9–3 g", "label": "precise stick-pack fills", "sort_order": 2}, headers=HDR)
    await client.post("/api/v1/content/hero/stats", json={"number": "24", "label": "items to choose from", "sort_order": 1}, headers=HDR)
    assert (await client.get("/api/v1/public/hero")).json()["stats"] == [
        {"number": "24", "label": "items to choose from"}, {"number": "0.9–3 g", "label": "precise stick-pack fills"}]


async def test_hero_admin_needs_content_edit(client):
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    assert (await client.get("/api/v1/content/hero")).status_code == 403
    assert (await client.post("/api/v1/content/hero/slides", json={"title": "Nope"}, headers=HDR)).status_code == 403
    assert (await client.post("/api/v1/content/hero/stats", json={"number": "1", "label": "nope"}, headers=HDR)).status_code == 403
    # Nor can they put pictures in the hero folder
    assert (await _upload(client, _jpeg(100, 100))).status_code == 403
