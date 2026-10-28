import re
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.catalog import Product
from app.seed_catalogue import CATALOGUE_CATEGORIES, PRODUCTS, add_catalogue

IMAGES = Path(__file__).parent.parent.parent / "frontend" / "public" / "images" / "products"
# The same line format the home page reads back (frontend/src/lib/catalogue.ts)
ITEM_LINE = re.compile(r"^• Item (\S+)(?: \((.+)\))?: (.+?), (\d+) pieces per box, (\d+) per case$")


async def test_catalogue_seed_adds_once_and_keeps_old_categories(client):
    async with AsyncSessionLocal() as db:
        await add_catalogue(db)
    async with AsyncSessionLocal() as db:
        await add_catalogue(db)  # second run adds nothing

    products = (await client.get("/api/v1/public/products")).json()
    assert len(products) == len(PRODUCTS) == len({p["slug"] for p in PRODUCTS})
    cats = {c["slug"]: c["product_count"] for c in (await client.get("/api/v1/public/categories")).json()}
    assert cats["coffee"] == 0  # the original category is kept
    assert sum(cats[slug] for slug, *_ in CATALOGUE_CATEGORIES) == len(PRODUCTS)


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
    for p in (await client.get("/api/v1/public/products")).json():
        lines = [line for line in p["description"].splitlines() if line.startswith("• ")]
        assert lines and all(ITEM_LINE.match(line) for line in lines), p["slug"]
        assert len(p["pack_formats"]) <= 255


def test_every_catalogue_product_has_its_picture():
    if not IMAGES.is_dir():
        pytest.skip("frontend folder not available (e.g. tests run inside the API image)")
    missing = [p["slug"] for p in PRODUCTS if not (IMAGES / f"{p['slug']}.jpg").is_file()]
    assert missing == []
