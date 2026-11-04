from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    """Application settings loaded from environment variables and ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "hml", "prod"] = "development"

    postgres_user: str = "app"
    postgres_password: str = "app"
    postgres_db: str = "customer_support_agent"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Optional full URL override, useful for managed databases.
    database_url: str | None = None

    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_recycle: int = 1800
    db_connect_timeout: float = 5.0
    db_healthcheck_timeout: float = 3.0

    db_startup_check_enabled: bool = True
    db_startup_max_retries: int = 10
    db_startup_retry_delay: float = 1.0

    @property
    def sqlalchemy_database_url(self) -> URL:
        """Return the async SQLAlchemy URL, honoring an explicit override."""
        if self.database_url:
            return make_url(self.database_url)

        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
