from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

# Neon's pooled URL goes through PgBouncer (transaction mode), which can't keep
# prepared statements between queries. Turning asyncpg's statement cache off fixes that.
engine = create_async_engine(
    settings.DATABASE_URL,
    # pool_pre_ping: check a pooled connection before using it. Without it, the first request
    # after Neon falls asleep (5 idle min) or the DB restarts fails with a 500 (found in the
    # 24 Oct end-to-end test). It costs one quick round trip; cheap once the DB is near the API.
    pool_pre_ping=True,
    pool_recycle=240,  # also replace connections every 4 min, before PgBouncer closes idle ones
    # Tests open a new event loop per test; pooled connections can't cross loops.
    **({"poolclass": NullPool} if settings.APP_ENV == "test" else {}),
    connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db():
    """FastAPI dependency: one DB session per request."""
    async with AsyncSessionLocal() as session:
        yield session
