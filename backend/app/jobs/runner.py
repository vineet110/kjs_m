"""Background jobs: a small loop inside the API process.

Every `jobs_interval_seconds` (config/app.ini), during `jobs_hours` on working days,
it runs each registered job once. Each job:
- gets its own DB session and a short job_run_id that appears on its log lines;
- runs under a Postgres advisory lock, so if we ever start two API processes the job
  still runs only once per tick;
- must be safe to run again (idempotent): it checks what's already done before acting.

Add a job:  @job("sla_check")  async def sla_check(db): ...  and import its module in
app/jobs/__init__.py. No Redis or Celery needed at our size.
"""
import asyncio
import logging
import uuid
import zlib
from datetime import datetime
from typing import Awaitable, Callable
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.ini import cfg
from app.core.database import AsyncSessionLocal
from app.core.logs import request_id_var

log = logging.getLogger("app.jobs")
JobFn = Callable[[AsyncSession], Awaitable[dict | None]]
JOBS: dict[str, JobFn] = {}
ANY_TIME: set[str] = set()  # jobs that also run outside jobs_hours (e.g. emails)
JOB_TIMEOUT_SECONDS = 300  # a stuck job is cancelled, so it can't block every other job forever


def job(name: str, any_time: bool = False):
    def register(fn: JobFn) -> JobFn:
        JOBS[name] = fn
        if any_time:
            ANY_TIME.add(name)
        return fn
    return register


def in_job_hours(now: datetime | None = None) -> bool:
    c = cfg().app
    now = now or datetime.now(ZoneInfo(c.timezone))
    if now.weekday() == 6:  # Sunday
        return False
    start, end = c.jobs_hours.split("-")
    return start <= now.strftime("%H:%M") < end


async def run_job(name: str) -> dict | None:
    """Run one job now (also used by tests and 'run now' buttons)."""
    run_id = uuid.uuid4().hex[:8]
    token = request_id_var.set(f"job-{run_id}")
    log.info("job.started", extra={"job": name, "job_run_id": run_id})
    try:
        async with AsyncSessionLocal() as db:
            lock_key = zlib.crc32(name.encode())
            got = await db.scalar(text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": lock_key})
            if not got:
                log.info("job.skipped_locked", extra={"job": name, "job_run_id": run_id})
                return None
            result = await asyncio.wait_for(JOBS[name](db), timeout=JOB_TIMEOUT_SECONDS) or {}
            await db.commit()
        log.info("job.finished", extra={"job": name, "job_run_id": run_id, **result})
        return result
    except Exception:
        log.exception("job.failed", extra={"job": name, "job_run_id": run_id})
        return None
    finally:
        request_id_var.reset(token)


async def loop() -> None:
    while True:
        try:
            if cfg().app.jobs_enabled:
                working = in_job_hours()
                for name in list(JOBS):
                    if working or name in ANY_TIME:
                        await run_job(name)
        except Exception:
            log.exception("jobs.loop_error")
        await asyncio.sleep(cfg().app.jobs_interval_seconds)
