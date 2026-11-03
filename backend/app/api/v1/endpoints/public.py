"""Public website API. No login. Only safe, published data goes out."""
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.files import send_file
from app.core.config.ini import public_config
from app.core.database import get_db
from app.core.deps import client_ip
from app.core.security import hash_ip
from app.schemas.catalog import CategoryOut, ProductOut
from app.schemas.common import Email, OneLine, Phone
from app.schemas.lead import LeadIn
from app.services import catalog_service, content_service, file_service, lead_service

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


@router.get("/files/{file_id}")
async def public_file(file_id: int, db: AsyncSession = Depends(get_db)):
    """Only files marked public (product images). Everything else is a 404 here."""
    return send_file(*await file_service.download(db, None, file_id), inline=True)


@router.get("/texts")
async def site_texts(db: AsyncSession = Depends(get_db)):
    """Editable page text + SEO (Admin > Website)."""
    return await content_service.texts(db, content_service.PUBLIC_KEYS)


@router.get("/offers")
async def offers(db: AsyncSession = Depends(get_db)):
    """Offers that are live right now (ticker on the home page)."""
    return await content_service.live_offers(db)


class PartnerIn(BaseModel):
    name: OneLine = Field(min_length=2, max_length=120)
    company: OneLine = Field(default="", max_length=200)
    partner_type: Literal["agent", "broker", "forwarder", "distributor", "other"]
    country: OneLine = Field(min_length=2, max_length=80)
    email: Email
    phone: Phone = Field(default="", max_length=30)
    message: str = Field(default="", max_length=2000)
    consent: Literal[True]
    website: str = Field(default="", max_length=255)  # honeypot


@router.post("/partners", status_code=201)
async def partner_apply(data: PartnerIn, request: Request, db: AsyncSession = Depends(get_db)):
    await content_service.apply_partner(db, data, hash_ip(client_ip(request)))
    return {"status": "received", "message": "Thank you! Our partnerships team will contact you."}


@router.get("/config")
async def config():
    """Feature switches + site name (same as /api/public/config, here for the frontend's API helper)."""
    return public_config()


@router.get("/products/{slug}/files")
async def product_files(slug: str, db: AsyncSession = Depends(get_db)):
    """Files marked "show on website" for this product (photos, spec sheets)."""
    return await file_service.public_files(db, "product", slug)
