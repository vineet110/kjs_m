from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_ENV: str = "development"
    SECRET_KEY: str = "super_secret_temporary_key_change_in_prod"
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://kjs_admin:kjs_secret_pass@localhost:5432/kjs_db"
    
    # External APIs
    ANTHROPIC_API_KEY: str = ""
    RESEND_API_KEY: str = ""
    WHATSAPP_API_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    
    # Storage
    FILE_STORAGE_PATH: str = "/srv/kjs_files"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
