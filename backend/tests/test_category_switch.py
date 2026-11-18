"""Category Show/Hide switch (Admin > Products): hiding a category takes it, its subcategories and all
their products off the public site and out of Koko; showing it brings them back."""
import pytest
from sqlalchemy import select

from app.core.config import ini
from app.core.database import AsyncSessionLocal
from app.models.audit import AuditLog
from app.models.catalog import Category, Product
from app.services import catalog_service
from tests.conftest import HDR, login, make_user

EDITOR = "cat@kjsindia.com"


@pytest.fixture
def modules(monkeypatch):
    def set_(**levels):
        for a, lv in levels.items():
            monkeypatch.setenv(f"KJS__MODULES__{a.upper()}", lv)
        ini.reload_now()
    yield set_
    monkeypatch.undo()
    ini.reload_now()


async def _catalogue() -> dict[str, int]:
    """Confectionery with its Wafers subcategory, plus Coffee (from conftest). One product in each. Ids by slug."""
    async with AsyncSessionLocal() as db:
        for slug, name in (("confectionery", "Confectionery"), ("wafers", "Wafers")):
            db.add(Category(slug=slug, name=name, description="", sort_order=5, is_active=True))
        await db.flush()
        cats = {c.slug: c.id for c in (await db.scalars(select(Category))).all()}
        for slug, cat in (("gofrey", "wafers"), ("choco-box", "confectionery"), ("stick-coffee", "coffee")):
            db.add(Product(category_id=cats[cat], slug=slug, name=slug))
        await db.commit()
    return cats


async def _editor(client):
    await make_user(EDITOR, permissions=["leads.view", "catalog.edit"])
    await login(client, EDITOR)


async def _switch(client, cat_id: int, on: bool, **extra):
    return await client.patch(f"/api/v1/admin/categories/{cat_id}", json={"is_active": on, **extra}, headers=HDR)


async def _public(client) -> tuple[set[str], set[str]]:
    cats = {c["slug"] for c in (await client.get("/api/v1/public/categories")).json()}
    prods = {p["slug"] for p in (await client.get("/api/v1/public/products")).json()}
    return cats, prods


async def test_hiding_a_category_takes_it_off_the_site_and_showing_brings_it_back(client):
    cats = await _catalogue()
    await _editor(client)
    r = await _switch(client, cats["wafers"], False)
    assert r.status_code == 200 and r.json()["is_active"] is False
    pub_cats, pub_prods = await _public(client)
    assert "wafers" not in pub_cats and "gofrey" not in pub_prods
    assert {"coffee", "confectionery"} <= pub_cats and {"stick-coffee", "choco-box"} <= pub_prods
    for path in ("/api/v1/public/categories/wafers", "/api/v1/public/products/gofrey"):
        assert (await client.get(path)).status_code == 404, path

    assert (await _switch(client, cats["wafers"], True)).status_code == 200
    pub_cats, pub_prods = await _public(client)
    assert "wafers" in pub_cats and "gofrey" in pub_prods
    assert (await client.get("/api/v1/public/products/gofrey")).status_code == 200


async def test_hiding_the_parent_hides_its_subcategories_and_keeps_their_own_switch(client):
    cats = await _catalogue()
    await _editor(client)
    await _switch(client, cats["confectionery"], False)
    pub_cats, pub_prods = await _public(client)
    assert pub_cats == {"coffee"} and pub_prods == {"stick-coffee"}
    assert (await client.get("/api/v1/public/products/gofrey")).status_code == 404
    assert (await client.get("/api/v1/public/categories/wafers")).status_code == 404
    # Wafers' own switch is untouched: it still says on, and comes back with its parent
    admin = {c["slug"]: c for c in (await client.get("/api/v1/admin/categories")).json()}
    assert admin["wafers"]["is_active"] is True and admin["wafers"]["parent"] == "confectionery"
    assert admin["wafers"]["visible"] is False
    await _switch(client, cats["confectionery"], True)
    assert (await _public(client))[0] == {"coffee", "confectionery", "wafers"}


async def test_koko_sees_only_switched_on_categories(client):
    cats = await _catalogue()
    await _editor(client)
    await _switch(client, cats["confectionery"], False)
    async with AsyncSessionLocal() as db:
        assert {c.slug for c in await catalog_service.list_categories(db)} == {"coffee"}
        assert {p.slug for p in await catalog_service.list_products(db)} == {"stick-coffee"}


async def test_admin_list_shows_hidden_categories_and_the_switch_is_audited(client):
    cats = await _catalogue()
    await _editor(client)
    await _switch(client, cats["coffee"], False)
    admin = {c["slug"]: c for c in (await client.get("/api/v1/admin/categories")).json()}
    assert set(admin) == {"coffee", "confectionery", "wafers"}
    assert admin["coffee"]["is_active"] is False and admin["coffee"]["visible"] is False
    assert admin["coffee"]["product_count"] == 1
    async with AsyncSessionLocal() as db:
        row = await db.scalar(select(AuditLog).where(AuditLog.action == "category.updated"))
    assert row.entity_id == str(cats["coffee"]) and row.before == {"is_active": True} and row.after == {"is_active": False}


async def test_switch_changes_only_is_active(client):
    cats = await _catalogue()
    await _editor(client)
    r = await _switch(client, cats["coffee"], False, name="Renamed", slug="renamed")
    assert r.status_code == 200
    async with AsyncSessionLocal() as db:
        c = await db.get(Category, cats["coffee"])
    assert (c.slug, c.name, c.is_active) == ("coffee", "Coffee", False)
    assert (await client.patch(f"/api/v1/admin/categories/{cats['coffee']}", json={}, headers=HDR)).status_code == 422


async def test_unknown_category_is_404(client):
    await _editor(client)
    assert (await _switch(client, 9999, False)).status_code == 404


async def test_without_catalog_edit_the_switch_is_refused(client):
    cats = await _catalogue()
    await make_user("e@kjsindia.com")
    await login(client, "e@kjsindia.com")
    assert (await client.get("/api/v1/admin/categories")).status_code == 403
    assert (await _switch(client, cats["coffee"], False)).status_code == 403


async def test_with_the_website_area_off_the_routes_are_off(client, modules):
    cats = await _catalogue()
    await make_user("admin@kjsindia.com", role="admin")
    await login(client, "admin@kjsindia.com")
    modules(website_admin="off")
    assert (await client.get("/api/v1/admin/categories")).json()["code"] == "module_off"
    assert (await _switch(client, cats["coffee"], False)).json()["code"] == "module_off"


async def test_a_product_can_still_be_edited_and_added_in_a_hidden_category(client):
    """Admin > Products works on hidden categories too (the form lists every category), so editing a wafer
    while Wafers is hidden keeps it in Wafers."""
    cats = await _catalogue()
    await _editor(client)
    await _switch(client, cats["wafers"], False)
    async with AsyncSessionLocal() as db:
        pid = await db.scalar(select(Product.id).where(Product.slug == "gofrey"))
    r = await client.patch(f"/api/v1/admin/products/{pid}", json={"category_slug": "wafers", "name": "Gofrey 2"}, headers=HDR)
    assert r.status_code == 200 and r.json()["category_slug"] == "wafers"
    r = await client.post("/api/v1/admin/products", json={"category_slug": "wafers", "name": "New Wafer"}, headers=HDR)
    assert r.status_code == 201
    assert "new-wafer" not in (await _public(client))[1]


async def test_showing_a_subcategory_of_a_hidden_parent_says_it_stays_hidden(client):
    """The admin page reads `visible` from the reply to say "Wafers stays hidden with Confectionery"."""
    cats = await _catalogue()
    await _editor(client)
    await _switch(client, cats["wafers"], False)
    await _switch(client, cats["confectionery"], False)
    r = (await _switch(client, cats["wafers"], True)).json()
    assert r["is_active"] is True and r["visible"] is False and r["parent"] == "confectionery"


async def test_category_page_is_404_when_the_list_has_no_match(client, monkeypatch):
    """The category route reads the list, then asks again only to raise the 404. If the category is switched
    on in between, it used to return nothing (a broken reply) instead of the 404."""
    await _catalogue()

    async def empty_list(db):
        return []
    monkeypatch.setattr(catalog_service, "list_categories", empty_list)  # as if Wafers was hidden at that moment
    r = await client.get("/api/v1/public/categories/wafers")
    assert r.status_code == 404 and r.json()["code"] == "not_found"


async def test_admin_list_switch_and_visibility_come_from_the_same_rows(client, monkeypatch):
    """`visible` is worked out from the rows the list returns, not from a second read (a switch in between
    could give is_active false with visible true)."""
    cats = await _catalogue()
    await _editor(client)
    await _switch(client, cats["coffee"], False)

    async def stale(db):
        return set()  # a second read taken before Coffee was hidden
    monkeypatch.setattr(catalog_service, "hidden_slugs", stale)
    admin = {c["slug"]: c for c in (await client.get("/api/v1/admin/categories")).json()}
    assert admin["coffee"]["is_active"] is False and admin["coffee"]["visible"] is False
