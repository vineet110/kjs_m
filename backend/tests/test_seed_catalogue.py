import re
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.catalog import Category, Product
from app.seed_catalogue import BEVERAGES, CATALOGUE_CATEGORIES, PRODUCTS, add_catalogue

IMAGES = Path(__file__).parent.parent.parent / "frontend" / "public" / "images" / "products"
# The same line format the home page reads back (frontend/src/lib/catalogue.ts)
ITEM_LINE = re.compile(r"^• Item (\S+)(?: \((.+)\))?: (.+?), (\d+) pieces per box, (\d+) per case$")


async def test_catalogue_seed_adds_once_and_keeps_old_categories(client):
    async with AsyncSessionLocal() as db:
        db.add(Category(slug="health-drinks", name="Health drinks", sort_order=3, is_active=True))  # from app.seed
        await db.commit()
        await add_catalogue(db)
    async with AsyncSessionLocal() as db:
        await add_catalogue(db)  # second run adds nothing

    products = (await client.get("/api/v1/public/products")).json()
    every = PRODUCTS + BEVERAGES
    assert len(products) == len(every) == len({p["slug"] for p in every})
    cats = {c["slug"]: c["product_count"] for c in (await client.get("/api/v1/public/categories")).json()}
    # The original categories are kept and get the coffee catalogue's products
    assert cats["coffee"] == sum(p["cat"] == "coffee" for p in BEVERAGES) == 4
    assert cats["health-drinks"] == 1
    assert sum(cats[slug] for slug, *_ in CATALOGUE_CATEGORIES) == len(every) - 5


async def test_catalogue_seed_works_on_a_fresh_database(client):
    # app.seed hasn't run: Coffee and Health drinks are created, so no product is skipped
    async with AsyncSessionLocal() as db:
        await add_catalogue(db)
    cats = {c["slug"]: c["product_count"] for c in (await client.get("/api/v1/public/categories")).json()}
    assert cats["coffee"] == 4 and cats["health-drinks"] == 1
    assert len((await client.get("/api/v1/public/products")).json()) == len(PRODUCTS) + len(BEVERAGES)


async def test_catalogue_seed_never_overwrites_admin_edits(client):
    async with AsyncSessionLocal() as db:
        await add_catalogue(db)
    async with AsyncSessionLocal() as db:
        p = await db.scalar(select(Product).where(Product.slug == "pacho-chocolate-bar"))
        p.name = "Renamed by admin"
        await db.commit()
    async with AsyncSessionLocal() as db:
        await add_catalogue(db)
    r = await client.get("/api/v1/public/products/pacho-chocolate-bar")
    assert r.json()["name"] == "Renamed by admin"


async def test_catalogue_descriptions_list_every_item(client):
    async with AsyncSessionLocal() as db:
        await add_catalogue(db)
    confectionery = {p["slug"] for p in PRODUCTS}  # the coffee catalogue has no item numbers
    for p in (await client.get("/api/v1/public/products")).json():
        if p["slug"] not in confectionery:
            assert "• " not in p["description"] and len(p["pack_formats"]) <= 255, p["slug"]
            continue
        lines = [line for line in p["description"].splitlines() if line.startswith("• ")]
        assert lines and all(ITEM_LINE.match(line) for line in lines), p["slug"]
        assert len(p["pack_formats"]) <= 255


def test_every_catalogue_product_has_its_picture():
    if not IMAGES.is_dir():
        pytest.skip("frontend folder not available (e.g. tests run inside the API image)")
    missing = [p["slug"] for p in PRODUCTS + BEVERAGES if not (IMAGES / f"{p['slug']}.jpg").is_file()]
    assert missing == []
