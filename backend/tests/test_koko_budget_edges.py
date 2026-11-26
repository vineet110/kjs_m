"""Edge cases for R72 (Koko's daily AI budget counted in the database)."""
import asyncio
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from app.core.config import ini
from app.core.database import AsyncSessionLocal
from app.models.koko_usage import KokoUsage
from app.services import koko_service


@pytest.fixture
def limit(monkeypatch):
    def set_to(n: int):
        monkeypatch.setenv("KJS__KOKO__DAILY_LIMIT", str(n))
        ini.reload_now()
    yield set_to
    monkeypatch.undo()
    ini.reload_now()


def _clock(monkeypatch, utc: datetime):
    class Fixed(datetime):
        @classmethod
        def now(cls, tz=None):
            return utc.astimezone(tz) if tz else utc.replace(tzinfo=None)
    monkeypatch.setattr(koko_service, "datetime", Fixed)


async def test_many_visitors_at_once_never_go_over_the_cap(limit):
    limit(10)
    results = await asyncio.gather(*[koko_service._within_daily_budget() for _ in range(25)])
    assert results.count(True) == 10
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(KokoUsage.calls)) == 25


async def test_the_day_turns_at_india_midnight_not_utc(limit, monkeypatch):
    limit(1)
    _clock(monkeypatch, datetime(2026, 11, 27, 18, 29, tzinfo=timezone.utc))  # 23:59 IST, 27 Nov
    assert await koko_service._within_daily_budget() is True
    assert await koko_service._within_daily_budget() is False
    _clock(monkeypatch, datetime(2026, 11, 27, 18, 31, tzinfo=timezone.utc))  # 00:01 IST, 28 Nov: a new budget
    assert await koko_service._within_daily_budget() is True
    async with AsyncSessionLocal() as db:
        days = dict((await db.execute(select(KokoUsage.day, KokoUsage.calls))).all())
    assert days == {date(2026, 11, 27): 2, date(2026, 11, 28): 1}


async def test_a_raised_limit_opens_the_budget_again_the_same_day(limit):
    limit(1)
    assert [await koko_service._within_daily_budget() for _ in range(2)] == [True, False]
    limit(5)
    assert await koko_service._within_daily_budget() is True


async def test_zero_limit_means_no_ai_calls(limit):
    limit(0)
    assert await koko_service._within_daily_budget() is False


async def test_no_database_means_no_ai_call(limit, monkeypatch):
    limit(10)

    class Broken:
        async def __aenter__(self):
            raise OSError("database down")

        async def __aexit__(self, *a):
            return False
    monkeypatch.setattr(koko_service, "AsyncSessionLocal", lambda: Broken())
    assert await koko_service._within_daily_budget() is False  # never an uncounted (unbudgeted) AI call
