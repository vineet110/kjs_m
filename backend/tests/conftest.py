"""Test setup: a throwaway Postgres (docker compose --profile test up -d test-db),
migrated once, emptied before every test. Tests never touch Neon."""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TEST_DB = os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://kjs_test:kjs_test@127.0.0.1:5433/kjs_test")
os.environ.update({
    "APP_ENV": "test",
    "DATABASE_URL": TEST_DB,
    "MIGRATION_DATABASE_URL": TEST_DB,
    "LLM_PROVIDER": "none",  # no real AI calls in tests
    "FIREBASE_SERVICE_ACCOUNT": "",  # never the real Firebase from tests (conftest fakes it)
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


# ---------- A fake Firebase (tests never call the real one) ----------
# A fake ID token names its account: id_token("e@kjsindia.com") signs in as e@kjsindia.com, whose Firebase uid
# is uid_of("e@kjsindia.com"). Anything else is refused like a fake or expired token.
FAKE_TOKEN = "fake-firebase-token:"
FAKE_UNVERIFIED = "fake-firebase-unverified:"


def uid_of(email: str) -> str:
    return f"uid-{email.lower()}"


def id_token(email: str, verified: bool = True, signed_in_seconds_ago: int = 0) -> str:
    return f"{FAKE_TOKEN if verified else FAKE_UNVERIFIED}{email}|{int(time.time()) - signed_in_seconds_ago}"


class FakeFirebase:
    def __init__(self):
        self.created: dict[str, str] = {}  # uid -> email (Firebase accounts that exist)
        self.deleted: list[str] = []
        self.disabled: dict[str, bool] = {}
        self.reset: dict[str, str] = {}  # uid -> one-time password set on a reused account
        self.valid_after_ms: dict[str, int] = {}  # uid -> when the password last changed (ms)

    async def verify_token(self, token: str) -> dict:
        for prefix, verified in ((FAKE_TOKEN, True), (FAKE_UNVERIFIED, False)):
            if token.startswith(prefix):
                email, signed_in_at = token[len(prefix):].rsplit("|", 1)
                return {"uid": uid_of(email), "email": email.lower(), "email_verified": verified,
                        "auth_time": int(signed_in_at), "valid_after_ms": self.valid_after_ms.get(uid_of(email), 0)}
        from app.core.firebase import BadToken
        raise BadToken("InvalidIdTokenError")

    async def create_user(self, email: str, password: str, name: str) -> str:
        self.created[uid_of(email)] = email
        return uid_of(email)

    async def ensure_user(self, email: str, password: str, name: str) -> str:
        return await self.create_user(email, password, name)

    async def uid_by_email(self, email: str) -> str | None:
        return next((uid for uid, e in self.created.items() if e == email), None)

    async def reset_account(self, uid: str, password: str, name: str) -> None:
        self.reset[uid] = password

    async def delete_user(self, uid: str) -> None:
        self.deleted.append(uid)

    async def set_disabled(self, uid: str, disabled: bool) -> None:
        self.disabled[uid] = disabled


@pytest.fixture(autouse=True)
def fake_firebase(monkeypatch):
    from app.core import firebase
    fake = FakeFirebase()
    for name in ("verify_token", "create_user", "ensure_user", "uid_by_email", "reset_account", "delete_user",
                 "set_disabled"):
        monkeypatch.setattr(firebase, name, getattr(fake, name))
    monkeypatch.setattr(firebase, "enabled", lambda: True)
    return fake


async def make_user(email: str, password: str = "password1234", role: str = "employee",
                    status: str = "active", permissions: list[str] | None = None, linked: bool = True):
    """A staff account. linked=False: an account from before Firebase (no firebase_uid yet).
    `password` is only for the old password hash of such accounts; Firebase keeps real passwords."""
    from app.core.security import hash_password
    from app.models.user import User
    async with AsyncSessionLocal() as db:
        if role == "admin":
            await auth_service.ensure_admin(db, email, password)
            return
        db.add(User(name=email.split("@")[0], email=email, password_hash=None if linked else hash_password(password),
                    firebase_uid=uid_of(email) if linked else None,
                    role=role, status=status, permissions=permissions or ["leads.view"]))
        await db.commit()


async def login(client: AsyncClient, email: str, password: str = "password1234"):
    """Logs in as this person (with a fake Firebase ID token; `password` is kept so old calls still read well)."""
    r = await client.post("/api/v1/auth/login", json={"id_token": id_token(email)}, headers=HDR)
    assert r.status_code == 200, r.text
    return r
