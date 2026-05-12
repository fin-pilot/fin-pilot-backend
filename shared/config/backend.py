from functools import lru_cache

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

from shared.config.paths import ENV_FILE


class BackendSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
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
def get_backend_settings() -> BackendSettings:
    return BackendSettings()


backend_settings = get_backend_settings()
