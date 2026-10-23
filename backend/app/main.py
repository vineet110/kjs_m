from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import install_error_handlers

app = FastAPI(
    title="KJS India Digital Platform API",
    version="0.1.0",
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["content-type", "x-requested-with"],
)
install_error_handlers(app)

app.include_router(api_router, prefix="/api/v1")


@app.get("/api/health")
async def health():
    """Is the process alive? (no DB call, so it's cheap for uptime checks)"""
    return {"status": "ok", "service": "kjs-api"}


@app.get("/api/health/ready")
async def ready(db: AsyncSession = Depends(get_db)):
    """Can we actually serve requests? Checks the database too."""
    await db.execute(text("SELECT 1"))
    return {"status": "ready", "database": "ok"}
