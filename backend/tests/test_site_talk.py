"""The site talks (PR C): the offer form's leads, its texts, and its settings."""
from tests.conftest import HDR, login, make_user

OFFER = {"source": "website_offer", "phone": "+91 98765 43210", "consent": True, "source_page": "/"}


async def test_offer_form_needs_only_a_phone_number(client):
    r = await client.post("/api/v1/public/leads", json=OFFER, headers=HDR)
    assert r.status_code == 201, r.text
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    lead = (await client.get("/api/v1/admin/leads")).json()[0]
    assert lead["source"] == "website_offer" and lead["name"] == "Website visitor (offer form)"


async def test_offer_form_still_needs_consent_and_a_real_phone(client):
    assert (await client.post("/api/v1/public/leads", json=OFFER | {"consent": False}, headers=HDR)).status_code == 422
    assert (await client.post("/api/v1/public/leads", json=OFFER | {"phone": "12"}, headers=HDR)).status_code == 422


async def test_other_forms_still_need_a_name(client):
    body = {"source": "enquiry_form", "phone": "+91 98765 43210", "consent": True}
    assert (await client.post("/api/v1/public/leads", json=body, headers=HDR)).status_code == 422
    assert (await client.post("/api/v1/public/leads", json=body | {"name": "   "}, headers=HDR)).status_code == 422
    assert (await client.post("/api/v1/public/leads", json=body | {"name": "Omar"}, headers=HDR)).status_code == 201


async def test_talk_texts_are_public_with_defaults(client):
    t = (await client.get("/api/v1/public/texts")).json()
    assert t["talk.sales"] == "Your sample is ready, just a click away." and "offer.terms" in t


async def test_popup_times_must_rise(client, monkeypatch):
    from app.core.config import ini
    monkeypatch.setenv("KJS__SITE_UI__POPUP_TIMES", "5, 3, 11")
    ini.reload_now()
    # Refused: the last good value stays
    assert (await client.get("/api/v1/public/config")).json()["site_ui"]["popup_times"] == [5, 8, 11, 15, 17, 25]


async def test_offer_form_is_refused_when_the_box_is_off(client, monkeypatch):
    from app.core.config import ini
    monkeypatch.setenv("KJS__SITE_UI__OFFER_BOX", "false")
    ini.reload_now()
    assert (await client.post("/api/v1/public/leads", json=OFFER, headers=HDR)).status_code == 404
