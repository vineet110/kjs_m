from tests.conftest import HDR, login, make_user

LEAD = {"name": "Lucia F", "email": "lucia@example.com", "company": "Iberia Foods",
        "category_slug": "coffee", "quantity": "20,000 sachets/month", "consent": True}


async def test_health(client):
    assert (await client.get("/api/health")).json()["status"] == "ok"
    assert (await client.get("/api/health/ready")).json()["database"] == "ok"


async def test_categories_and_empty_products(client):
    cats = (await client.get("/api/v1/public/categories")).json()
    assert cats[0]["slug"] == "coffee" and cats[0]["product_count"] == 0
    assert (await client.get("/api/v1/public/products")).json() == []


async def test_unknown_product_404_has_standard_shape(client):
    r = await client.get("/api/v1/public/products/nope")
    assert r.status_code == 404
    assert set(r.json()) == {"code", "message", "details", "request_id"}


async def test_lead_saved_and_visible_to_employee(client):
    r = await client.post("/api/v1/public/leads", json=LEAD)
    assert r.status_code == 201
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    leads = (await client.get("/api/v1/employee/leads")).json()
    assert leads[0]["company"] == "Iberia Foods" and leads[0]["category_name"] == "Coffee"


async def test_lead_requires_consent_and_contact(client):
    assert (await client.post("/api/v1/public/leads", json={**LEAD, "consent": False})).status_code == 422
    assert (await client.post("/api/v1/public/leads", json={**LEAD, "email": None, "phone": ""})).status_code == 422


async def test_honeypot_pretends_success_but_saves_nothing(client):
    r = await client.post("/api/v1/public/leads", json={**LEAD, "website": "http://spam"})
    assert r.status_code == 201
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    assert (await client.get("/api/v1/admin/stats")).json()["leads_total"] == 0


async def test_lead_rate_limit(client):
    for _ in range(5):
        assert (await client.post("/api/v1/public/leads", json=LEAD)).status_code == 201
    assert (await client.post("/api/v1/public/leads", json=LEAD)).status_code == 429


async def test_product_created_by_admin_shows_publicly(client):
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    r = await client.post("/api/v1/admin/products", headers=HDR, json={
        "category_slug": "coffee", "name": "Instant Coffee 3-in-1 Stick", "pack_formats": "Stick pack 18 g"})
    assert r.status_code == 201
    p = (await client.get("/api/v1/public/products/instant-coffee-3-in-1-stick")).json()
    assert p["category_name"] == "Coffee"


async def test_koko_falls_back_when_llm_is_off(client):
    r = await client.post("/api/v1/koko/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200
    assert "+91 97037 35666" in r.json()["reply"]
