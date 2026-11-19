"""Website showcase (Admin > Website): partner logos for the sliding strip, activity lines for pop-ups."""
import io
from datetime import datetime, timedelta, timezone

from PIL import Image

from tests.conftest import HDR, login, make_user


async def _editor(client):
    await make_user("web@kjsindia.com", permissions=["leads.view", "content.edit"])
    await login(client, "web@kjsindia.com")


def _png(w: int, h: int) -> bytes:
    b = io.BytesIO()
    Image.new("RGBA", (w, h), (20, 60, 160, 255)).save(b, "PNG")
    return b.getvalue()


async def _logo(client, folder: str = "partners"):
    return await client.post("/api/v1/files", data={"owner_type": "website", "owner_id": folder, "is_public": "true"},
                             files={"file": ("nestle.png", _png(2000, 800), "image/png")}, headers=HDR)


def _ago(**kw) -> str:
    return (datetime.now(timezone.utc) - timedelta(**kw)).isoformat()


async def test_public_lists_are_empty_until_admin_adds(client):
    # Empty: the strip keeps its built-in names and no pop-up shows
    assert (await client.get("/api/v1/public/brand-partners")).json() == []
    assert (await client.get("/api/v1/public/activity")).json() == []


async def test_partner_with_logo_is_public_and_logo_is_shrunk(client):
    await _editor(client)
    up = await _logo(client)
    assert up.status_code == 201, up.text
    fid = up.json()["id"]
    assert (await client.post("/api/v1/content/showcase/partners", json={"name": "Nestlé", "logo_file_id": fid, "sort_order": 1}, headers=HDR)).status_code == 201
    assert (await client.post("/api/v1/content/showcase/partners", json={"name": "Mayora", "sort_order": 0}, headers=HDR)).status_code == 201
    await client.post("/api/v1/content/showcase/partners", json={"name": "Hidden", "is_active": False}, headers=HDR)
    assert (await client.get("/api/v1/public/brand-partners")).json() == [
        {"name": "Mayora", "logo": None}, {"name": "Nestlé", "logo": f"/api/v1/public/files/{fid}"}]
    client.cookies.clear()
    pic = Image.open(io.BytesIO((await client.get(f"/api/v1/public/files/{fid}")).content))
    assert max(pic.size) == 1600 and pic.mode == "RGBA"  # smaller, and the transparent background is kept


async def test_partner_logo_must_be_a_partners_picture(client):
    await _editor(client)
    hero_pic = (await _logo(client, folder="hero")).json()["id"]
    r = await client.post("/api/v1/content/showcase/partners", json={"name": "Unilever", "logo_file_id": hero_pic}, headers=HDR)
    assert r.status_code == 422
    assert (await client.post("/api/v1/content/showcase/partners", json={"name": "   "}, headers=HDR)).status_code == 422


async def test_removing_a_logo_keeps_the_name(client):
    await _editor(client)
    fid = (await _logo(client)).json()["id"]
    p = (await client.post("/api/v1/content/showcase/partners", json={"name": "Unilever", "logo_file_id": fid}, headers=HDR)).json()
    r = await client.patch(f"/api/v1/content/showcase/partners/{p['id']}", json={"logo_file_id": None}, headers=HDR)
    assert r.status_code == 200 and r.json()["logo"] is None and r.json()["name"] == "Unilever"


async def test_activity_lines_recent_true_and_in_order(client, monkeypatch):
    from app.core.config import ini
    monkeypatch.setenv("KJS__SITE_UI__ACTIVITY_MAX_AGE_DAYS", "30")
    ini.reload_now()
    await _editor(client)
    for text, when, order in [("A brand in Dubai requested a sample", _ago(hours=2), 0),
                              ("A distributor in Pune asked for a quote", _ago(days=1), 0),
                              ("Old news from last year", _ago(days=200), 0)]:
        r = await client.post("/api/v1/content/showcase/activity", json={"text": text, "happened_at": when, "sort_order": order}, headers=HDR)
        assert r.status_code == 201, r.text
    await client.post("/api/v1/content/showcase/activity", json={"text": "Paused line here", "happened_at": _ago(hours=1), "is_active": False}, headers=HDR)
    shown = [x["text"] for x in (await client.get("/api/v1/public/activity")).json()]
    # Newest first; older than activity_max_age_days and switched-off lines stay hidden
    assert shown == ["A brand in Dubai requested a sample", "A distributor in Pune asked for a quote"]


async def test_activity_time_cannot_be_in_the_future(client):
    await _editor(client)
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    r = await client.post("/api/v1/content/showcase/activity", json={"text": "Shipped to Dubai", "happened_at": future}, headers=HDR)
    assert r.status_code == 422
    # A time without a time zone is refused (it would be read wrongly)
    r = await client.post("/api/v1/content/showcase/activity", json={"text": "Shipped to Dubai", "happened_at": "2026-11-19T10:00:00"}, headers=HDR)
    assert r.status_code == 422


async def test_partner_limit_from_site_ui_ini(client, monkeypatch):
    from app.core.config import ini
    monkeypatch.setenv("KJS__SITE_UI__PARTNERS_MAX", "1")
    ini.reload_now()
    await _editor(client)
    a = (await client.post("/api/v1/content/showcase/partners", json={"name": "Nestlé"}, headers=HDR)).json()
    assert (await client.post("/api/v1/content/showcase/partners", json={"name": "Unilever"}, headers=HDR)).status_code == 422
    # Editing the one already on is fine
    assert (await client.patch(f"/api/v1/content/showcase/partners/{a['id']}", json={"name": "Nestlé India"}, headers=HDR)).status_code == 200


async def test_showcase_admin_needs_content_edit(client):
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    for path in ("/api/v1/content/showcase/partners", "/api/v1/content/showcase/activity"):
        assert (await client.get(path)).status_code == 403
    assert (await client.post("/api/v1/content/showcase/partners", json={"name": "Nope"}, headers=HDR)).status_code == 403
    assert (await client.post("/api/v1/content/showcase/activity", json={"text": "Nope nope", "happened_at": _ago(hours=1)}, headers=HDR)).status_code == 403
    assert (await _logo(client)).status_code == 403
