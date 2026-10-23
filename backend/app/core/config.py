from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables (or the repo-root .env).

    Anything that may change between laptop / staging / production lives here,
    so moving from Neon to the company server is a config change, not a code change.
    """

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    APP_ENV: str = "development"
    SECRET_KEY: str = "dev_only_change_me"
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Database: app uses the pooled URL; migrations use the direct URL when given.
    DATABASE_URL: str = "postgresql+asyncpg://kjs_admin:kjs_secret_pass@localhost:5432/kjs_db"
    MIGRATION_DATABASE_URL: str = ""

    # Sessions
    SESSION_COOKIE_NAME: str = "kjs_session"
    SESSION_DAYS: int = 7

    # Koko (LLM). Provider is swappable via env (backlog D4).
    LLM_PROVIDER: str = "groq"  # groq | anthropic | none
    LLM_MODEL: str = "openai/gpt-oss-120b"
    GROQ_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # First admin, created by `python -m app.seed`
    FIRST_ADMIN_EMAIL: str = ""
    FIRST_ADMIN_PASSWORD: str = ""

    # Other providers (later phases)
    RESEND_API_KEY: str = ""
    WHATSAPP_API_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""

    # Storage: local disk now, Cloudflare R2 later (backlog D16)
    FILE_STORAGE_PATH: str = "./storage"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


settings = Settings()
