from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class BackendSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    DATABASE_URL: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    HF_TOKEN: str | None = None
    APP_NAME: str = "Personal Finance Management System"
    DEBUG: bool = False


@lru_cache
def get_backend_settings():
    return BackendSettings()


backend_settings = get_backend_settings()