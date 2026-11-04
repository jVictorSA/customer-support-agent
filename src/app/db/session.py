import asyncio
import logging
from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.sqlalchemy_database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle,
        connect_args={"timeout": settings.db_connect_timeout},
    )


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_engine(),
        expire_on_commit=False,
        autoflush=False,
    )


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide one ``AsyncSession`` per request.

    Repository methods own their transactions and commit/rollback explicitly.
    The session is only closed here.
    """
    async with get_session_factory()() as session:
        yield session


async def wait_for_database(*, max_retries: int, retry_delay: float) -> bool:
    """Try to connect to the database during application startup.

    Returns ``True`` as soon as a ``SELECT 1`` succeeds, otherwise ``False``
    after all attempts. Callers should start in degraded mode on failure.
    """
    if max_retries <= 0:
        return False

    for attempt in range(1, max_retries + 1):
        try:
            async with get_engine().connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception:
            is_last_attempt = attempt == max_retries
            logger.warning(
                "Database connection attempt %s/%s failed",
                attempt,
                max_retries,
                exc_info=is_last_attempt,
            )
            if not is_last_attempt:
                await asyncio.sleep(retry_delay)
        else:
            logger.info("Database connection established on attempt %s", attempt)
            return True

    return False
