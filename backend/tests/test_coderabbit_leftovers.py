"""CodeRabbit points still open after the 27 Nov merges: each test breaks the old code on purpose."""
import pytest
from sqlalchemy import update

from app.core.database import AsyncSessionLocal
from app.models.catalog import Product
from tests.conftest import HDR, login, make_user
from tests.test_product_items import ITEM


async def _product(client, items=None):
    await make_user("cat@kjsindia.com", permissions=["leads.view", "catalog.edit"])
    await login(client, "cat@kjsindia.com")
    return await client.post("/api/v1/admin/products", headers=HDR,
                             json={"category_slug": "coffee", "name": "Rabbit Coffee", "items": items or [ITEM]})


# ---- #138: the Admin "Items" box uses "|" and new lines, so an item may not contain them ----

@pytest.mark.parametrize("field,value", [
    ("variant", "Hazel | nut"), ("variant", "Hazel\nnut"), ("variant", "Hazel\r\nnut"), ("variant", "a\tb"),
    ("weight", "25 g\n"), ("weight", "25|g"), ("no", "80|1"),
])
async def test_an_item_with_a_separator_in_it_is_refused(client, field, value):
    r = await _product(client, [{**ITEM, field: value}])
    assert r.status_code == 422


@pytest.mark.parametrize("variant", ["Haselnuß", "Café crème", "Hazelnut 🌰", "Dark (70%)"])
async def test_ordinary_and_unicode_item_text_is_still_accepted(client, variant):
    r = await _product(client, [{**ITEM, "variant": variant}])
    assert r.status_code == 201 and r.json()["items"][0]["variant"] == variant


# ---- #138: one bad stored item must never break the product list or page ----

async def test_bad_stored_items_are_skipped_or_defaulted_never_a_500(client):
    p = (await _product(client)).json()
    bad = [ITEM, {"no": "802", "weight": "1 kg", "pieces": None, "per_case": None}, "junk", None,
           {"variant": "no number"}, {"no": 803, "weight": 5, "pieces": "x", "per_case": 2}]
    async with AsyncSessionLocal() as db:
        await db.execute(update(Product).where(Product.id == p["id"]).values(items=bad))
        await db.commit()
    client.cookies.clear()
    lst = await client.get("/api/v1/public/products")
    page = await client.get(f"/api/v1/public/products/{p['slug']}")
    assert lst.status_code == 200 and page.status_code == 200
    items = page.json()["items"]
    assert items[0] == ITEM  # the good one is still there, first
    assert [i["no"] for i in items] == ["801", "802", "803"]  # no number: skipped; a number as a number: text
    assert items[1]["pieces"] == 0 and items[2]["pieces"] == 0  # null or not a number: 0, never an error


# ---- #123: a phone-only row is the same buyer as a saved one with an email and that phone ----

async def _import(client, name, csv):
    r = await client.post("/api/v1/assign/import", files={"file": (name, csv.encode(), "text/csv")}, headers=HDR)
    return r.json()


async def test_a_phone_only_row_matches_a_saved_buyer_that_has_an_email(client):
    await make_user("boss@kjsindia.com", permissions=["leads.view", "assign.manage"])
    await login(client, "boss@kjsindia.com")
    await _import(client, "1.csv", "Company,Email,Phone,Category\nAcme,a@acme.com,04011111111,coffee\n")
    r = await _import(client, "2.csv", "Company,Email,Phone,Category\n"
                                       "Acme,,+91 40 1111 1111,coffee\n"     # same buyer, no email: skipped
                                       "Acme,b@acme.com,04011111111,coffee\n"  # another person, same office line
                                       "Other Co,,04011111111,coffee\n")       # same phone, another company
    # which row matters: row 2 (the phone-only one) is the duplicate, rows 3 and 4 are new buyers
    assert r["added"] == 2 and r["skipped"] == [{"row": 2, "reason": "already imported"}]


async def test_inside_one_file_a_phone_only_row_after_an_email_row_is_skipped(client):
    await make_user("boss@kjsindia.com", permissions=["leads.view", "assign.manage"])
    await login(client, "boss@kjsindia.com")
    r = await _import(client, "1.csv", "Company,Email,Phone,Category\n"
                                       "Acme,a@acme.com,04011111111,coffee\nAcme,,040-1111-1111,coffee\n")
    assert r["added"] == 1 and len(r["skipped"]) == 1


# ---- #130: an error answer is never kept by a browser or proxy ----

async def test_error_answers_are_never_cached(client):
    r = await client.get("/api/v1/public/files/999999")  # 404
    assert r.status_code == 404 and r.headers["cache-control"] == "no-store"
    r = await client.post("/api/v1/public/leads", json={}, headers=HDR)  # 422
    assert r.status_code == 422 and r.headers["cache-control"] == "no-store"


async def test_a_successful_public_answer_keeps_its_own_cache_policy(client):
    r = await client.get("/api/v1/public/products")
    assert r.status_code == 200 and r.headers.get("cache-control") != "no-store"
