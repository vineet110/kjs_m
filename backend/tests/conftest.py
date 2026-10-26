"""Test setup: a throwaway Postgres (docker compose --profile test up -d test-db),
migrated once, emptied before every test. Tests never touch Neon."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

TEST_DB = os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://kjs_test:kjs_test@127.0.0.1:5433/kjs_test")
os.environ.update({
    "APP_ENV": "test",
    "DATABASE_URL": TEST_DB,
    "MIGRATION_DATABASE_URL": TEST_DB,
    "LLM_PROVIDER": "none",  # no real AI calls in tests
    "SECRET_KEY": "test-secret",
    "STORAGE_DRIVER": "local",
    "FILE_STORAGE_PATH": tempfile.mkdtemp(prefix="kjs-test-files-"),
})

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.core.rate_limit import reset_all as reset_rate_limits  # noqa: E402
from app.main import app  # noqa: E402
from app.services import auth_service  # noqa: E402

BACKEND = Path(__file__).parent.parent
HDR = {"x-requested-with": "kjs"}


def pytest_sessionstart(session):
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, check=True, env=os.environ.copy())


@pytest.fixture(autouse=True)
async def clean_db():
    # TRUNCATE is allowed on audit_log (the trigger blocks row UPDATE/DELETE only).
    async with engine.begin() as conn:
        tables = (await conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
        ))).scalars().all()
        await conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
        await conn.execute(text(
            "INSERT INTO categories (slug, name, description, sort_order, is_active) "
            "VALUES ('coffee', 'Coffee', 'Coffee things', 1, true)"
        ))
    reset_rate_limits()
    yield


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def make_user(email: str, password: str = "password1234", role: str = "employee",
                    status: str = "active", permissions: list[str] | None = None):
    from app.core.security import hash_password
    from app.models.user import User
    async with AsyncSessionLocal() as db:
        if role == "admin":
            await auth_service.ensure_admin(db, email, password)
            return
        db.add(User(name=email.split("@")[0], email=email, password_hash=hash_password(password),
                    role=role, status=status, permissions=permissions or ["leads.view"]))
        await db.commit()


async def login(client: AsyncClient, email: str, password: str = "password1234"):
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password}, headers=HDR)
    assert r.status_code == 200, r.text
    return r
