"""Website content (texts, offers, Koko facts/transcripts), partners, gated leads, profile,
analytics, alerts, settings view."""
from tests.conftest import HDR, login, make_user

PARTNER = {"name": "Ravi", "partner_type": "forwarder", "country": "UAE", "email": "ravi@ship.ae", "consent": True}


async def _editor(client):
    await make_user("web@kjsindia.com", permissions=["leads.view", "content.edit"])
    await login(client, "web@kjsindia.com")


async def test_texts_default_override_reset(client):
    default = (await client.get("/api/v1/public/texts")).json()["home.hero_title"]
    assert default and "koko.facts" not in (await client.get("/api/v1/public/texts")).json()
    await _editor(client)
    r = await client.put("/api/v1/content/texts/home.hero_title", json={"value": "Coffee sticks, made right"}, headers=HDR)
    assert r.status_code == 204
    assert (await client.get("/api/v1/public/texts")).json()["home.hero_title"] == "Coffee sticks, made right"
    await client.put("/api/v1/content/texts/home.hero_title", json={"value": None}, headers=HDR)
    assert (await client.get("/api/v1/public/texts")).json()["home.hero_title"] == default
    assert (await client.put("/api/v1/content/texts/nope", json={"value": "x"}, headers=HDR)).status_code == 404


async def test_offers_only_live_ones_are_public(client):
    await _editor(client)
    await client.post("/api/v1/content/offers", json={"text": "Free samples for distributors"}, headers=HDR)
    await client.post("/api/v1/content/offers", json={"text": "Old offer", "ends_at": "2020-01-01T00:00:00Z"}, headers=HDR)
    await client.post("/api/v1/content/offers", json={"text": "Paused", "is_active": False}, headers=HDR)
    assert [o["text"] for o in (await client.get("/api/v1/public/offers")).json()] == ["Free samples for distributors"]
    r = await client.post("/api/v1/content/offers", json={"text": "Bad", "starts_at": "2026-02-01T00:00:00Z", "ends_at": "2026-01-01T00:00:00Z"}, headers=HDR)
    assert r.status_code == 422


async def test_content_needs_permission(client):
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    for path in ("/api/v1/content/texts", "/api/v1/content/offers", "/api/v1/content/koko-chats", "/api/v1/content/partners"):
        assert (await client.get(path)).status_code == 403


async def test_partner_application_and_review(client):
    await make_user("m@kjsindia.com", permissions=["leads.view", "leads.view_all"])
    r = await client.post("/api/v1/public/partners", json=PARTNER, headers=HDR)
    assert r.status_code == 201
    assert (await client.post("/api/v1/public/partners", json=PARTNER | {"consent": False}, headers=HDR)).status_code == 422
    await login(client, "m@kjsindia.com")
    apps = (await client.get("/api/v1/content/partners")).json()
    assert [a["name"] for a in apps] == ["Ravi"]
    assert (await client.post(f"/api/v1/content/partners/{apps[0]['id']}/status", json={"status": "approved"}, headers=HDR)).status_code == 204
    assert (await client.get("/api/v1/employee/notifications")).json()["unread"] == 1


async def test_referral_partner_keeps_saved_value_broker(client):
    # "Broker" is shown as "Referral partner"; the saved value stays "broker", so older applications still match
    await make_user("m@kjsindia.com", permissions=["leads.view", "leads.view_all"])
    assert (await client.post("/api/v1/public/partners", json=PARTNER | {"partner_type": "broker"}, headers=HDR)).status_code == 201
    await login(client, "m@kjsindia.com")
    assert [a["partner_type"] for a in (await client.get("/api/v1/content/partners")).json()] == ["broker"]
    bell = (await client.get("/api/v1/employee/notifications")).json()["items"]
    assert bell[0]["title"] == "Partner application: Ravi (Referral partner, UAE)"
    assert "broker" not in (await client.get("/api/v1/public/texts")).json()["partners.intro"].lower()


def test_partner_labels_match_the_types_the_api_accepts():
    # One label per accepted type, so a new type can't reach staff as a raw value
    # (the frontend keeps the same list in lib/partners.ts)
    from typing import get_args

    from app.api.v1.endpoints.public import PartnerIn
    from app.services.content_service import PARTNER_LABELS
    assert set(get_args(PartnerIn.model_fields["partner_type"].annotation)) == set(PARTNER_LABELS)


async def test_koko_saves_transcript_and_uses_edited_facts(client):
    # LLM is off in tests -> fallback reply, but the transcript is still kept
    body = {"messages": [{"role": "user", "content": "Do you make tea premix?"}], "chat_id": "abc-123", "page": "/"}
    assert (await client.post("/api/v1/koko/chat", json=body, headers=HDR)).status_code == 200
    await _editor(client)
    chats = (await client.get("/api/v1/content/koko-chats")).json()
    assert chats["total"] == 1 and chats["items"][0]["messages"][0]["content"] == "Do you make tea premix?"
    facts = next(t for t in (await client.get("/api/v1/content/texts")).json() if t["key"] == "koko.facts")
    assert "KJS" in facts["value"] and facts["changed"] is False


async def test_gated_action_creates_lead_with_its_source(client):
    body = {"source": "price_sheet", "name": "Omar", "email": "omar@alnoor.ae", "consent": True, "product_slug": "nope"}
    assert (await client.post("/api/v1/public/leads", json=body, headers=HDR)).status_code == 201
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    assert (await client.get("/api/v1/admin/leads")).json()[0]["source"] == "price_sheet"


async def test_profile_and_password(client):
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    r = await client.patch("/api/v1/auth/profile", json={"name": "Esha K", "notify_email": False}, headers=HDR)
    assert r.json()["name"] == "Esha K" and r.json()["notify_email"] is False
    bad = await client.post("/api/v1/auth/password", json={"current": "wrong-password", "new": "a-new-password-1"}, headers=HDR)
    assert bad.status_code == 422
    ok = await client.post("/api/v1/auth/password", json={"current": "password1234", "new": "a-new-password-1"}, headers=HDR)
    assert ok.status_code == 204
    assert (await client.get("/api/v1/auth/me")).status_code == 200  # this browser stays logged in
    await login(client, "e@kjsindia.com", "a-new-password-1")


async def test_analytics_alerts_config_for_admin_only(client):
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    for path in ("/api/v1/admin/analytics", "/api/v1/admin/alerts", "/api/v1/admin/config"):
        assert (await client.get(path)).status_code == 403
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    a = (await client.get("/api/v1/admin/analytics")).json()
    assert len(a["leads_per_week"]) == 8 and len(a["attendance"]) == 14 and a["sla"]["answered"] == 0
    assert (await client.get("/api/v1/admin/alerts")).json()["rules"]["board_thresholds"] == [50, 85, 100]
    cfgs = {c["key"]: c for c in (await client.get("/api/v1/admin/config")).json()}
    assert cfgs["sla.respond_minutes"]["source"] == "ini" and cfgs["sla.respond_minutes"]["value"] == 20


async def test_edit_and_hide_product(client):
    await make_user("cat@kjsindia.com", permissions=["leads.view", "catalog.edit"])
    await login(client, "cat@kjsindia.com")
    p = (await client.post("/api/v1/admin/products", json={"category_slug": "coffee", "name": "Filter Coffee"}, headers=HDR)).json()
    body = {"category_slug": "coffee", "name": "Filter Coffee 80:20", "moq": "10,000 units"}
    r = await client.patch(f"/api/v1/admin/products/{p['id']}", json=body, headers=HDR)
    assert r.json()["name"] == "Filter Coffee 80:20" and r.json()["slug"] == p["slug"]
    await client.patch(f"/api/v1/admin/products/{p['id']}", json=body | {"is_active": False}, headers=HDR)
    assert (await client.get(f"/api/v1/public/products/{p['slug']}")).status_code == 404
