"""Seed data that must exist in every environment. Safe to run many times.

Run:  python -m app.seed      (from the backend/ folder)

Products are NOT seeded: KJS hasn't sent the product list yet (backlog I2).
Admin adds them in the admin console, so the site never shows made-up products.
"""
import asyncio

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.catalog import Category
from app.services import auth_service

CATEGORIES = [
    ("coffee", "Coffee", "Instant coffee, coffee premixes and 3-in-1 blends, packed in stick packs, sachets, pouches and jars.", 1),
    ("tea", "Tea", "Tea premixes and instant tea blends in single-serve and bulk packs.", 2),
    ("health-drinks", "Health drinks", "Malt, cocoa and nutritional drink powders, blended in our ribbon blenders.", 3),
    ("confectionery", "Confectionery", "Cocoa-based and speciality confectionery, with ball milling for smooth texture.", 4),
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        existing = set((await db.scalars(select(Category.slug))).all())
        added = 0
        for slug, name, desc, order in CATEGORIES:
            if slug not in existing:
                db.add(Category(slug=slug, name=name, description=desc, sort_order=order, is_active=True))
                added += 1
        await db.commit()
        print(f"categories: {added} added, {len(existing)} already there")

        if settings.FIRST_ADMIN_EMAIL and settings.FIRST_ADMIN_PASSWORD:
            created = await auth_service.ensure_admin(db, settings.FIRST_ADMIN_EMAIL, settings.FIRST_ADMIN_PASSWORD)
            print(f"admin {settings.FIRST_ADMIN_EMAIL}: {'created' if created else 'already exists'}")
        else:
            print("FIRST_ADMIN_EMAIL / FIRST_ADMIN_PASSWORD not set: no admin created")


if __name__ == "__main__":
    asyncio.run(main())
