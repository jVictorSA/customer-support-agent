from functools import lru_cache
from typing import Literal
from urllib.parse import quote

from pydantic import SecretStr, field_validator
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

    # Document ingestion -------------------------------------------------
    documents_max_upload_mb: int = 50
    documents_max_pages: int = 500
    documents_storage_bucket: str = "rag-documents"
    documents_ocr_enabled: bool = False
    documents_ocr_languages: str = "por+eng"
    documents_chunk_target_tokens: int = 800
    documents_chunk_max_tokens: int = 1000
    documents_chunk_min_tokens: int = 150
    documents_chunk_overlap_tokens: int = 60
    documents_parser_version: str = "docling-1"
    documents_chunking_version: str = "hierarchical-1"
    documents_summary_version: str = "deepseek-flash-1"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: SecretStr = SecretStr("minioadmin")
    minio_secure: bool = False

    rabbitmq_user: str = "app"
    rabbitmq_password: SecretStr = SecretStr("app")
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    celery_broker_url: str | None = None
    celery_max_retries: int = 3
    celery_task_soft_time_limit: int = 1500
    celery_task_time_limit: int = 1800

    jina_api_key: SecretStr | None = None
    jina_base_url: str = "https://api.jina.ai/v1"
    jina_embedding_model: str = "jina-embeddings-v5-text-small"
    jina_embedding_dimensions: int = 1024
    jina_timeout: float = 60.0
    jina_batch_size: int = 16
    jina_batch_max_tokens: int = 16000
    jina_max_retries: int = 10
    jina_rpm: int = 100
    jina_tpm: int = 100_000

    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"
    deepseek_timeout: float = 120.0
    deepseek_max_retries: int = 5
    deepseek_summary_max_tokens: int = 800
    deepseek_summary_input_max_tokens: int = 6000
    deepseek_disable_thinking: bool = True

    @field_validator("jina_api_key", "deepseek_api_key", mode="before")
    @classmethod
    def _empty_secret_is_none(cls, value: object) -> object:
        return None if value == "" else value

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
    def rabbitmq_url(self) -> str:
        """Return the AMQP broker URL, honoring an explicit override."""
        if self.celery_broker_url:
            return self.celery_broker_url
        password = quote(
            self.rabbitmq_password.get_secret_value(), safe=""
        )
        user = quote(self.rabbitmq_user, safe="")
        return (
            f"amqp://{user}:{password}"
            f"@{self.rabbitmq_host}:{self.rabbitmq_port}//"
        )

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
