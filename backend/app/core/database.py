from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings

# Neon's pooled URL goes through PgBouncer (transaction mode), which can't keep
# prepared statements between queries. Turning asyncpg's statement cache off fixes that.
engine = create_async_engine(
    settings.DATABASE_URL,
    # No pool_pre_ping: it costs one extra DB round trip per request (~0.5 s to Neon in Ohio).
    # Instead, replace connections every 4 min, before Neon/PgBouncer closes idle ones.
    pool_recycle=240,
    # Tests open a new event loop per test; pooled connections can't cross loops.
    **({"poolclass": NullPool} if settings.APP_ENV == "test" else {}),
    connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db():
    """FastAPI dependency: one DB session per request."""
    async with AsyncSessionLocal() as session:
        yield session
