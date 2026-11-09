import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

from app.core.config import settings
from app.models.base import Base
# Import all models for Alembic autogenerate
import app.models  # noqa: F401

# Migrations use the direct (non-pooled) URL when one is set. On the server they must: the app's own
# database user can't change tables, and the running API never gets that URL (CR11), so deploy.sh and
# restore.sh hand it to the migration step. Locally an empty value falls back to DATABASE_URL.
if settings.is_production and not settings.MIGRATION_DATABASE_URL:
    raise SystemExit("MIGRATION_DATABASE_URL is empty: on the server, run migrations through deploy.sh "
                     "(it passes the value from deploy/.env).")
DB_URL = settings.MIGRATION_DATABASE_URL or settings.DATABASE_URL

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = DB_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = DB_URL
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
