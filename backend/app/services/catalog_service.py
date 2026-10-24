import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.permissions import effective_permissions
from app.models.catalog import Category, Product
from app.models.user import User
from app.schemas.catalog import CategoryOut, ProductIn, ProductOut
from app.services import audit_service, file_service


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:110]


def _product_out(p: Product, c: Category) -> ProductOut:
    return ProductOut(
        id=p.id, slug=p.slug, name=p.name, description=p.description, pack_formats=p.pack_formats,
        moq=p.moq, image_path=p.image_path, private_label=p.private_label,
        is_best_seller=p.is_best_seller, category_slug=c.slug, category_name=c.name, is_active=p.is_active,
    )


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
        .where(Category.is_active)
        .order_by(Category.sort_order, Category.name)
    )
    return [
        CategoryOut(id=c.id, slug=c.slug, name=c.name, description=c.description, product_count=n)
        for c, n in rows.all()
    ]


async def get_category(db: AsyncSession, slug: str) -> Category:
    c = await db.scalar(select(Category).where(Category.slug == slug, Category.is_active))
    if c is None:
        raise AppError(404, "not_found", "Category not found.")
    return c


async def list_products(
    db: AsyncSession, category_slug: str | None = None, best_sellers: bool = False, include_hidden: bool = False
) -> list[ProductOut]:
    q = (
        select(Product, Category)
        .join(Category, Category.id == Product.category_id)
        .order_by(Product.name)
    )
    if not include_hidden:  # the admin list shows hidden products too, so they can be shown again
        q = q.where(Product.is_active, Category.is_active)
    if category_slug:
        q = q.where(Category.slug == category_slug)
    if best_sellers:
        q = q.where(Product.is_best_seller)
    return [_product_out(p, c) for p, c in (await db.execute(q)).all()]


async def get_product(db: AsyncSession, slug: str) -> ProductOut:
    row = (
        await db.execute(
            select(Product, Category)
            .join(Category, Category.id == Product.category_id)
            .where(Product.slug == slug, Product.is_active)
        )
    ).first()
    if row is None:
        raise AppError(404, "not_found", "Product not found.")
    return _product_out(*row)


async def create_product(db: AsyncSession, actor: User, data: ProductIn) -> ProductOut:
    category = await get_category(db, data.category_slug)
    slug = slugify(data.name)
    if await db.scalar(select(func.count()).select_from(Product).where(Product.slug == slug)):
        raise AppError(409, "duplicate", "A product with this name already exists.")
    p = Product(
        category_id=category.id, slug=slug, name=data.name.strip(), description=data.description,
        pack_formats=data.pack_formats, moq=data.moq, image_path=data.image_path,
        private_label=data.private_label, is_best_seller=data.is_best_seller, is_active=True,
    )
    db.add(p)
    await db.flush()
    audit_service.record(db, actor=actor, action="product.created", entity_type="product",
                         entity_id=p.id, after=data.model_dump())
    await db.commit()
    return _product_out(p, category)


async def update_product(db: AsyncSession, actor: User, product_id: int, data: ProductIn, is_active: bool = True) -> ProductOut:
    """Edit a product. The slug (web address) stays the same so links and files keep working."""
    p = await db.get(Product, product_id)
    if p is None:
        raise AppError(404, "not_found", "Product not found.")
    category = await get_category(db, data.category_slug)
    before = {"name": p.name, "category_id": p.category_id, "moq": p.moq, "is_active": p.is_active}
    p.category_id, p.name, p.description = category.id, data.name.strip(), data.description
    p.pack_formats, p.moq, p.image_path = data.pack_formats, data.moq, data.image_path
    p.private_label, p.is_best_seller, p.is_active = data.private_label, data.is_best_seller, is_active
    audit_service.record(db, actor=actor, action="product.updated", entity_type="product", entity_id=p.id,
                         before=before, after=data.model_dump() | {"is_active": is_active})
    await db.commit()
    return _product_out(p, category)


# ---------- Product files (images, spec PDFs) ----------
async def _product_files_access(db: AsyncSession, user: User, owner_id: str, action: str) -> bool:
    return action == "read" or "catalog.edit" in effective_permissions(user.role, user.permissions)


file_service.register_owner("product", _product_files_access)
