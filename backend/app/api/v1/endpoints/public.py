"""Public website API. No login. Only safe, published data goes out."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import client_ip
from app.core.security import hash_ip
from app.schemas.catalog import CategoryOut, ProductOut
from app.schemas.lead import LeadIn
from app.services import catalog_service, lead_service

router = APIRouter()


@router.get("/categories", response_model=list[CategoryOut])
async def categories(db: AsyncSession = Depends(get_db)):
    return await catalog_service.list_categories(db)


@router.get("/categories/{slug}", response_model=CategoryOut)
async def category(slug: str, db: AsyncSession = Depends(get_db)):
    for c in await catalog_service.list_categories(db):
        if c.slug == slug:
            return c
    await catalog_service.get_category(db, slug)  # raises the standard 404


@router.get("/products", response_model=list[ProductOut])
async def products(category: str | None = None, best_sellers: bool = False, db: AsyncSession = Depends(get_db)):
    return await catalog_service.list_products(db, category, best_sellers)


@router.get("/products/{slug}", response_model=ProductOut)
async def product(slug: str, db: AsyncSession = Depends(get_db)):
    return await catalog_service.get_product(db, slug)


@router.post("/leads", status_code=201)
async def create_lead(data: LeadIn, request: Request, db: AsyncSession = Depends(get_db)):
    await lead_service.create(db, data, hash_ip(client_ip(request)))
    return {"status": "received", "message": "Thank you! Our sales team will contact you soon."}
