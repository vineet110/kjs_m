import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import app.jobs  # noqa: F401  (registers background jobs)
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.config.ini import public_config
from app.core.database import get_db
from app.core.errors import install_error_handlers
from app.core.logs import RequestContextMiddleware, setup_logging
from app.jobs import runner

setup_logging()
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info("app.started", extra={"env": settings.APP_ENV, "jobs": list(runner.JOBS)})
    # Tests run jobs directly (runner.run_job), never on a timer.
    task = None if settings.APP_ENV == "test" else asyncio.create_task(runner.loop())
    yield
    if task:
        task.cancel()
    log.info("app.stopped")


app = FastAPI(
    title="KJS India Digital Platform API",
    version="0.2.0",
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["content-type", "x-requested-with", "x-request-id", "idempotency-key"],
)
app.add_middleware(RequestContextMiddleware)  # added last = runs first: request ID + timing log
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


@app.get("/api/public/config")
async def config_for_frontend():
    """Safe values only (feature switches, site name). Never secrets."""
    return public_config()
