"""R19: a product's catalogue items have their own column, checked on save."""
import importlib.util
from pathlib import Path

from tests.conftest import HDR, login, make_user

ITEM = {"no": "801", "variant": "Hazelnut", "weight": "25 g", "pieces": 24, "per_case": 6}


async def test_items_are_saved_edited_and_returned(client):
    await make_user("cat@kjsindia.com", permissions=["leads.view", "catalog.edit"])
    await login(client, "cat@kjsindia.com")
    p = (await client.post("/api/v1/admin/products", headers=HDR,
                           json={"category_slug": "coffee", "name": "Item Coffee", "items": [ITEM]})).json()
    assert p["items"] == [ITEM]
    r = await client.patch(f"/api/v1/admin/products/{p['id']}", headers=HDR,
                           json={"items": [ITEM, {**ITEM, "no": "802", "variant": ""}]})
    assert r.status_code == 200 and [i["no"] for i in r.json()["items"]] == ["801", "802"]
    public = (await client.get(f"/api/v1/public/products/{p['slug']}")).json()
    assert len(public["items"]) == 2


async def test_a_wrong_item_is_refused_not_dropped(client):
    await make_user("cat@kjsindia.com", permissions=["leads.view", "catalog.edit"])
    await login(client, "cat@kjsindia.com")
    for bad in ({**ITEM, "pieces": 0}, {**ITEM, "no": "80 1"}, {**ITEM, "weight": ""}):
        r = await client.post("/api/v1/admin/products", headers=HDR,
                              json={"category_slug": "coffee", "name": "Bad Item Coffee", "items": [bad]})
        assert r.status_code == 422


def _migration():
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0036_product_items.py"
    spec = importlib.util.spec_from_file_location("m0036", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_migration_moves_item_lines_out_of_the_description_and_back():
    m = _migration()
    text = ("Crunchy wafers.\n\nItems in our catalogue:\n"
            "• Item 801 (Hazelnut): 25 g, 24 pieces per box, 6 per case\n"
            "• Item 802: 40 g, 12 pieces per box, 8 per case")
    description, items = m.split_description(text)
    assert description == "Crunchy wafers."
    assert items == [ITEM, {"no": "802", "variant": "", "weight": "40 g", "pieces": 12, "per_case": 8}]
    assert [m.item_line(i) for i in items] == text.split("\n")[3:]


def test_the_migration_leaves_a_line_it_cannot_store_where_it_was():
    m = _migration()
    long_weight = "• Item 803: 25 g pouch, approx, family pack size, more, 24 pieces per box, 6 per case"
    text = ("Wafers.\n\nItems in our catalogue:\n• Item 801: 25 g, 24 pieces per box, 6 per case\n"
            + long_weight + "\n• Item 801: 30 g, 24 pieces per box, 6 per case")  # a repeated number too
    description, items = m.split_description(text)
    assert [i["no"] for i in items] == ["801"]
    assert "Items in our catalogue:" in description and long_weight in description  # kept, with its header


async def test_the_same_item_number_twice_is_refused(client):
    await make_user("cat@kjsindia.com", permissions=["leads.view", "catalog.edit"])
    await login(client, "cat@kjsindia.com")
    r = await client.post("/api/v1/admin/products", headers=HDR,
                          json={"category_slug": "coffee", "name": "Twice Coffee", "items": [ITEM, ITEM]})
    assert r.status_code == 422


async def test_an_odd_stored_item_never_breaks_the_product_list(client):
    from sqlalchemy import update
    from app.core.database import AsyncSessionLocal
    from app.models.catalog import Product
    await make_user("cat@kjsindia.com", permissions=["leads.view", "catalog.edit"])
    await login(client, "cat@kjsindia.com")
    p = (await client.post("/api/v1/admin/products", headers=HDR,
                           json={"category_slug": "coffee", "name": "Odd Coffee"})).json()
    async with AsyncSessionLocal() as db:
        await db.execute(update(Product).where(Product.id == p["id"]).values(
            items=[{"no": "x", "variant": "", "weight": "w" * 50, "pieces": 0, "per_case": 0}]))
        await db.commit()
    assert (await client.get("/api/v1/public/products")).status_code == 200
