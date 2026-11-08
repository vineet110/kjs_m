import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.router import api_router
from app.core.config import production_problems, settings
from app.core.config.ini import public_config
from app.core.database import engine, get_db
from app.core.errors import AppError
from app.core.errors import install_error_handlers
from app.core.logs import RequestContextMiddleware, setup_logging
from app.jobs import runner
from app.services import (  # noqa: F401  (importing them registers their background jobs)
    assign_service, board_service, file_service, lead_service, notification_service,
)

setup_logging()
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if problems := production_problems(settings):
        for p in problems:
            log.critical("config.unsafe_for_production", extra={"problem": p})
        raise RuntimeError("Refusing to start in production: " + "; ".join(problems))
    log.info("app.started", extra={"env": settings.APP_ENV, "jobs": list(runner.JOBS)})
    # Tests run jobs directly (runner.run_job), never on a timer.
    task = None if settings.APP_ENV == "test" else asyncio.create_task(runner.loop())
    if task:
        task.add_done_callback(_loop_ended)
    yield
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    await engine.dispose()  # close DB connections cleanly
    log.info("app.stopped")


def _loop_ended(task: asyncio.Task) -> None:
    if not task.cancelled() and task.exception():
        log.critical("jobs.loop_died", exc_info=task.exception())


app = FastAPI(
    title="KJS India Digital Platform API",
    version="0.2.0",
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",  # no API map for strangers
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
    """Can we actually serve requests? Checks the database and that background jobs still run."""
    await db.execute(text("SELECT 1"))
    if not runner.loop_is_alive():
        raise AppError(503, "jobs_stalled", "Background jobs have stopped (SLA alerts, emails).")
    return {"status": "ready", "database": "ok", "jobs": "ok"}


@app.get("/api/public/config")
async def config_for_frontend():
    """Safe values only (feature switches, site name). Never secrets."""
    return public_config()
