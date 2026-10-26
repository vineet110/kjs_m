"""Production refuses to start with laptop settings (default secret, localhost URLs...)."""
from app.core.config import Settings, production_problems

GOOD = dict(
    APP_ENV="production",
    SECRET_KEY="x" * 48,
    DATABASE_URL="postgresql+asyncpg://kjs:real-password@db:5432/kjs",
    PUBLIC_BASE_URL="https://www.kjsindia.com",
    ALLOWED_ORIGINS="https://www.kjsindia.com",
    STORAGE_DRIVER="local",
)


def make(**overrides) -> Settings:
    # _env_file=None: ignore the developer's .env so the test only sees these values
    return Settings(_env_file=None, **{**GOOD, **overrides})


def test_good_production_settings_pass():
    assert production_problems(make()) == []


def test_development_is_never_checked():
    assert production_problems(make(APP_ENV="development", SECRET_KEY="dev_only_change_me")) == []


def test_each_unsafe_value_is_reported():
    cases = {
        "SECRET_KEY": make(SECRET_KEY="dev_only_change_me"),
        "short": make(SECRET_KEY="too-short"),
        "DATABASE_URL": make(DATABASE_URL="postgresql+asyncpg://kjs_admin:kjs_secret_pass@db/kjs"),
        "PUBLIC_BASE_URL": make(PUBLIC_BASE_URL="http://localhost:3000"),
        "ALLOWED_ORIGINS": make(ALLOWED_ORIGINS="https://www.kjsindia.com,http://localhost:3000"),
        "R2": make(STORAGE_DRIVER="r2", R2_ACCOUNT_ID="abc"),
    }
    for name, s in cases.items():
        assert len(production_problems(s)) == 1, name
