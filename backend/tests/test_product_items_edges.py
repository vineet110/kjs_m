"""Edge cases for R19 (products.items and migration 0036)."""
from tests.conftest import HDR, login, make_user
from tests.test_product_items import ITEM, _migration

I1 = "• Item 801 (Hazelnut): 25 g, 24 pieces per box, 6 per case"


def test_the_migration_reads_windows_line_ends_and_stray_spaces():
    m = _migration()
    for text in (f"Crunchy.\r\n\r\nItems in our catalogue:\r\n{I1}\r\n", f"Crunchy.\n\nItems in our catalogue:\n  {I1}  "):
        assert m.split_description(text) == ("Crunchy.", [ITEM])


def test_the_migration_handles_only_items_empty_and_none():
    m = _migration()
    assert m.split_description(f"Items in our catalogue:\n{I1}") == ("", [ITEM])
    assert m.split_description("") == ("", [])
    assert m.split_description(None) == ("", [])


def test_text_after_the_items_stays():
    m = _migration()
    description, items = m.split_description(f"Crunchy.\n\nItems in our catalogue:\n{I1}\n\nMore text after.")
    assert items == [ITEM] and description.startswith("Crunchy.") and description.endswith("More text after.")


async def _staff(client):
    await make_user("cat@kjsindia.com", permissions=["leads.view", "catalog.edit"])
    await login(client, "cat@kjsindia.com")
    return (await client.post("/api/v1/admin/products", headers=HDR,
                              json={"category_slug": "coffee", "name": "Edge Coffee", "items": [ITEM]})).json()


async def test_items_null_is_refused_and_an_empty_list_clears_them(client):
    p = await _staff(client)
    url = f"/api/v1/admin/products/{p['id']}"
    assert (await client.patch(url, headers=HDR, json={"items": None})).status_code == 422  # never a 500 (NOT NULL)
    r = await client.patch(url, headers=HDR, json={"name": "Edge Coffee 2"})  # items not sent: kept
    assert r.status_code == 200 and r.json()["items"] == [ITEM]
    r = await client.patch(url, headers=HDR, json={"items": []})
    assert r.status_code == 200 and r.json()["items"] == []


async def test_too_many_or_odd_items_are_refused(client):
    p = await _staff(client)
    url = f"/api/v1/admin/products/{p['id']}"
    many = [{**ITEM, "no": str(n)} for n in range(101)]
    for bad in (many, [{**ITEM, "no": "8\t1"}], [{**ITEM, "pieces": "lots"}], [{**ITEM, "per_case": 100001}],
                [{**ITEM, "variant": "v" * 61}], ["801"], {"no": "801"}):
        assert (await client.patch(url, headers=HDR, json={"items": bad})).status_code == 422, bad


async def test_a_unicode_variant_is_kept(client):
    p = await _staff(client)
    r = await client.patch(f"/api/v1/admin/products/{p['id']}", headers=HDR,
                           json={"items": [{**ITEM, "variant": "इलायची café"}]})
    assert r.status_code == 200 and r.json()["items"][0]["variant"] == "इलायची café"


async def test_items_need_catalog_edit(client):
    p = await _staff(client)
    await make_user("e@kjsindia.com", permissions=["leads.view"])
    await login(client, "e@kjsindia.com")
    r = await client.patch(f"/api/v1/admin/products/{p['id']}", headers=HDR, json={"items": []})
    assert r.status_code == 403
