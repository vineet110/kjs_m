import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.permissions import effective_permissions
from app.models.catalog import Category, Product
from app.models.file import StoredFile
from app.models.user import User
from app.schemas.catalog import AdminCategoryOut, CategoryOut, ProductIn, ProductOut
from app.services import audit_service, file_service


# Categories shown inside another one: the parent's page and count include its subcategories' products.
# The database keeps them as separate categories. Same list in frontend/src/lib/catalogue.ts (menu layout).
SUBCATEGORIES: dict[str, list[str]] = {
    "confectionery": ["chocolate-bars", "wafers", "biscuits", "marshmallow-cakes"],
}
PARENT_OF: dict[str, str] = {child: parent for parent, kids in SUBCATEGORIES.items() for child in kids}


def range_text(cats: list[CategoryOut]) -> str:
    """The categories shown, in words ("coffee, health drinks and confectionery"): top level only. Same rule as
    rangeText in frontend/src/lib/catalogue.ts. No categories: the full range."""
    names = [c.name.lower() for c in cats if c.slug not in PARENT_OF]
    if not names:
        return "coffee, tea, health drinks and confectionery"
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


async def hidden_slugs(db: AsyncSession) -> set[str]:
    """Categories off the public site: switched off in Admin > Products, or inside a parent that is.
    Worked out when reading, so a subcategory keeps its own switch: showing the parent again brings
    back only the subcategories that were on."""
    off = set((await db.scalars(select(Category.slug).where(Category.is_active.is_(False)))).all())
    return _with_children(off)


def _with_children(off: set[str]) -> set[str]:
    """Switched-off slugs plus the subcategories of the switched-off parents."""
    return off | {child for child, parent in PARENT_OF.items() if parent in off}


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:110]


def _product_out(p: Product, c: Category, photo_url: str | None = None) -> ProductOut:
    return ProductOut(
        id=p.id, slug=p.slug, name=p.name, description=p.description, pack_formats=p.pack_formats,
        moq=p.moq, image_path=p.image_path, private_label=p.private_label,
        is_best_seller=p.is_best_seller, offer_percent=p.offer_percent, category_slug=c.slug, category_name=c.name,
        is_active=p.is_active, items=p.items or [], photo_url=photo_url,
    )


async def _first_photos(db: AsyncSession, slugs: list[str]) -> dict[str, str]:
    """The first photo uploaded with "Show on website" ticked, per product slug. The cards use it when the
    product has no image path (a photo uploaded in Admin > Products). Same address the product page uses."""
    if not slugs:
        return {}
    rows = await db.execute(
        select(StoredFile.owner_id, func.min(StoredFile.id))
        .where(StoredFile.owner_type == "product", StoredFile.owner_id.in_(slugs), StoredFile.is_public.is_(True),
               StoredFile.deleted_at.is_(None), StoredFile.content_type.like("image/%"))
        .group_by(StoredFile.owner_id)
    )
    return {slug: f"/api/v1/public/files/{file_id}" for slug, file_id in rows.all()}


async def list_categories(db: AsyncSession) -> list[CategoryOut]:
    counts = (
        select(Product.category_id, func.count().label("n"))
        .where(Product.is_active)
        .group_by(Product.category_id)
        .subquery()
    )
    rows = await db.execute(
        select(Category, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.category_id == Category.id)
        .where(Category.slug.not_in(await hidden_slugs(db)))
        .order_by(Category.sort_order, Category.name)
    )
    rows = rows.all()
    own = {c.slug: n for c, n in rows}
    return [
        CategoryOut(
            id=c.id, slug=c.slug, name=c.name, description=c.description,
            product_count=n + sum(own.get(s, 0) for s in SUBCATEGORIES.get(c.slug, [])),
        )
        for c, n in rows
    ]


async def get_category(db: AsyncSession, slug: str, include_hidden: bool = False) -> Category:
    """include_hidden: Admin > Products, where products of a hidden category can still be added and edited."""
    c = await db.scalar(select(Category).where(Category.slug == slug))
    if c is None or (not include_hidden and c.slug in await hidden_slugs(db)):
        raise AppError(404, "not_found", "Category not found.")
    return c


async def admin_categories(db: AsyncSession) -> list[AdminCategoryOut]:
    """Every category, hidden ones too (so they can be shown again), with its own switch and whether the
    public site shows it (a subcategory of a hidden parent is off the site whatever its own switch says)."""
    counts = dict((await db.execute(select(Product.category_id, func.count()).group_by(Product.category_id))).all())
    cats = (await db.scalars(select(Category).order_by(Category.sort_order, Category.name))).all()
    # From these same rows (not a second read), so a row's switch and "visible" always agree
    hidden = _with_children({c.slug for c in cats if not c.is_active})
    return [_admin_category_out(c, hidden, counts.get(c.id, 0)) for c in cats]


def _admin_category_out(c: Category, hidden: set[str], product_count: int) -> AdminCategoryOut:
    return AdminCategoryOut(id=c.id, slug=c.slug, name=c.name, is_active=c.is_active, visible=c.slug not in hidden,
                            parent=PARENT_OF.get(c.slug), product_count=product_count)


async def set_category_active(db: AsyncSession, actor: User, category_id: int, is_active: bool) -> AdminCategoryOut:
    """The Show/Hide switch. Changes only is_active; the audit row goes in the same transaction.
    The row is locked while it is read, so two admins switching at once can't log a change that wasn't made.
    The reply is built before the commit: if that fails, the switch and its audit row roll back together."""
    c = await db.get(Category, category_id, with_for_update=True)
    if c is None:
        raise AppError(404, "not_found", "Category not found.")
    before = c.is_active
    c.is_active = is_active
    audit_service.record(db, actor=actor, action="category.updated", entity_type="category", entity_id=c.id,
                         before={"is_active": before}, after={"is_active": is_active})
    await db.flush()
    count = await db.scalar(select(func.count()).select_from(Product).where(Product.category_id == c.id))
    out = _admin_category_out(c, await hidden_slugs(db), count or 0)
    await db.commit()
    return out


async def list_products(
    db: AsyncSession, category_slug: str | None = None, best_sellers: bool = False, include_hidden: bool = False
) -> list[ProductOut]:
    q = (
        select(Product, Category)
        .join(Category, Category.id == Product.category_id)
        .order_by(Product.name)
    )
    if not include_hidden:  # the admin list shows hidden products too, so they can be shown again
        q = q.where(Product.is_active, Category.slug.not_in(await hidden_slugs(db)))
    if category_slug:
        q = q.where(Category.slug.in_([category_slug, *SUBCATEGORIES.get(category_slug, [])]))
    if best_sellers:
        q = q.where(Product.is_best_seller)
    rows = (await db.execute(q)).all()
    photos = await _first_photos(db, [p.slug for p, _ in rows])
    return [_product_out(p, c, photos.get(p.slug)) for p, c in rows]


async def get_product(db: AsyncSession, slug: str) -> ProductOut:
    row = (
        await db.execute(
            select(Product, Category)
            .join(Category, Category.id == Product.category_id)
            .where(Product.slug == slug, Product.is_active)
        )
    ).first()
    # A product of a hidden category (or of a subcategory of one) is off the site, like the category
    if row is None or row[1].slug in await hidden_slugs(db):
        raise AppError(404, "not_found", "Product not found.")
    p, c = row
    return _product_out(p, c, (await _first_photos(db, [p.slug])).get(p.slug))


async def create_product(db: AsyncSession, actor: User, data: ProductIn) -> ProductOut:
    category = await get_category(db, data.category_slug, include_hidden=True)
    slug = slugify(data.name)
    if await db.scalar(select(func.count()).select_from(Product).where(Product.slug == slug)):
        raise AppError(409, "duplicate", "A product with this name already exists.")
    p = Product(
        category_id=category.id, slug=slug, name=data.name.strip(), description=data.description,
        pack_formats=data.pack_formats, moq=data.moq, image_path=data.image_path,
        private_label=data.private_label, is_best_seller=data.is_best_seller, offer_percent=data.offer_percent,
        is_active=True, items=[i.model_dump() for i in data.items],
    )
    db.add(p)
    await db.flush()
    audit_service.record(db, actor=actor, action="product.created", entity_type="product",
                         entity_id=p.id, after=data.model_dump())
    await db.commit()
    return _product_out(p, category)


async def update_product(db: AsyncSession, actor: User, product_id: int, changes: dict) -> ProductOut:
    """Edit a product: only the fields in `changes` (the ones the client sent); the rest stay as they are.
    The slug (web address) stays the same so links and files keep working."""
    p = await db.get(Product, product_id)
    if p is None:
        raise AppError(404, "not_found", "Product not found.")
    if "category_slug" in changes:
        category = await get_category(db, changes.pop("category_slug"), include_hidden=True)
        changes["category_id"] = category.id
    else:
        category = await db.get(Category, p.category_id)
    before = {k: getattr(p, k) for k in changes}
    for k, v in changes.items():
        setattr(p, k, v)
    # The audit log keeps what was really saved, field by field
    audit_service.record(db, actor=actor, action="product.updated", entity_type="product", entity_id=p.id,
                         before=before, after={k: getattr(p, k) for k in changes})
    await db.commit()
    return _product_out(p, category)


# ---------- Product files (images, spec PDFs) ----------
async def _product_files_access(db: AsyncSession, user: User, owner_id: str, action: str) -> bool:
    if action == "read":
        return True
    # Uploads only to a product that exists (not to a typo slug, where nobody would ever see them)
    return ("catalog.edit" in effective_permissions(user.role, user.permissions)
            and bool(await db.scalar(select(Product.id).where(Product.slug == owner_id))))


async def _product_is_live(db: AsyncSession, slug: str) -> bool:
    return bool(await db.scalar(select(Product.id).join(Category, Category.id == Product.category_id)
                                .where(Product.slug == slug, Product.is_active,
                                       Category.slug.not_in(await hidden_slugs(db)))))


file_service.register_owner("product", _product_files_access, public=_product_is_live)
