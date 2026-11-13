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

    # Email (any SMTP server: Zoho, Gmail Workspace, SES…). Empty host = emails are skipped (logged).
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "KJS India <no-reply@kjsindia.com>"  # also the sender for Brevo
    # Brevo HTTP API (brevo.com, free 300 emails/day). Set = emails go through Brevo instead of SMTP
    # (Render's free tier blocks SMTP). The sender in SMTP_FROM must be verified in Brevo.
    BREVO_API_KEY: str = ""
    # Full URL of the site, used for links inside emails
    PUBLIC_BASE_URL: str = "http://localhost:3000"

    # Other providers (later phases)
    RESEND_API_KEY: str = ""
    WHATSAPP_API_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""

    # Storage (backlog D16): "local" folder in dev, "r2" (Cloudflare R2) in production
    STORAGE_DRIVER: str = "local"
    FILE_STORAGE_PATH: str = "./storage"
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET: str = ""
    # Off-site backup bucket (kjs-bkp-prod) and its OWN key: given only to deploy/backup.sh, never to the app
    R2_BACKUP_BUCKET: str = ""
    R2_BACKUP_ACCESS_KEY_ID: str = ""
    R2_BACKUP_SECRET_ACCESS_KEY: str = ""

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


# Values that only make sense on a laptop. Production must never start with them.
DEV_SECRET_KEYS = {"dev_only_change_me", "change_this_to_a_secure_random_key_in_production"}


def production_problems(s: Settings) -> list[str]:
    """Settings that are unsafe in production. The app refuses to start if any are found,
    so a missing .env value shows up at deploy time, not as a security hole later."""
    if not s.is_production:
        return []
    problems = []
    if s.SECRET_KEY in DEV_SECRET_KEYS or len(s.SECRET_KEY) < 32:
        problems.append("SECRET_KEY is a default or shorter than 32 characters")
    if "kjs_secret_pass" in s.DATABASE_URL:
        problems.append("DATABASE_URL uses the example password")
    if not s.PUBLIC_BASE_URL.startswith("https://"):
        problems.append("PUBLIC_BASE_URL must be the real https:// address")
    if "localhost" in s.ALLOWED_ORIGINS or "127.0.0.1" in s.ALLOWED_ORIGINS:
        problems.append("ALLOWED_ORIGINS still lists localhost")
    others = [o.strip() for o in s.ALLOWED_ORIGINS.split(",") if "localhost" not in o and "127.0.0.1" not in o]
    if any(not o.startswith("https://") for o in others):
        problems.append("ALLOWED_ORIGINS must list only https:// addresses (never *)")
    if s.STORAGE_DRIVER == "r2" and not all((s.R2_ACCOUNT_ID, s.R2_ACCESS_KEY_ID, s.R2_SECRET_ACCESS_KEY, s.R2_BUCKET)):
        problems.append("STORAGE_DRIVER=r2 but an R2_* value is empty")
    return problems


settings = Settings()
