"""R72: Koko's daily AI budget is counted in the database, so a restart doesn't reset it."""
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.koko_usage import KokoUsage
from app.services import koko_service


async def test_the_daily_budget_is_counted_in_the_database(monkeypatch):
    monkeypatch.setenv("KJS__KOKO__DAILY_LIMIT", "2")
    from app.core.config import ini
    ini.reload_now()
    assert [await koko_service._within_daily_budget() for _ in range(3)] == [True, True, False]
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(KokoUsage.calls)) == 3  # still there for the next process / after a restart
