import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.session import get_engine, get_session_factory

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_TEXT_TO_SQL_ROLE = "text_to_sql_reader"
_TEXT_TO_SQL_DEFAULT_PASSWORD = "dev-only-text-to-sql-password"


def _text_to_sql_password() -> str:
    configured = get_settings().text_to_sql_db_password
    if configured is not None:
        return configured.get_secret_value()
    return os.getenv(
        "TEXT_TO_SQL_DB_PASSWORD", _TEXT_TO_SQL_DEFAULT_PASSWORD
    )


@pytest.fixture(scope="session")
def test_database_name() -> str:
    explicit_test_db = os.getenv("POSTGRES_TEST_DB")
    if explicit_test_db:
        return explicit_test_db

    database = os.getenv("POSTGRES_DB", "customer_support_agent_test")
    if not database.endswith("_test"):
        raise RuntimeError(
            "Integration tests must target a test database ending in '_test'; "
            f"got {database!r}. Set POSTGRES_TEST_DB explicitly if needed."
        )
    return database


def _ensure_text_to_sql_role(test_database_name: str) -> None:
    previous = os.environ.get("POSTGRES_DB")
    os.environ["POSTGRES_DB"] = test_database_name
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    settings = get_settings()
    url = settings.sqlalchemy_database_url

    async def run() -> None:
        engine = create_async_engine(url, poolclass=NullPool)
        try:
            async with engine.begin() as connection:
                exists = await connection.scalar(
                    text(
                        "SELECT 1 FROM pg_roles WHERE rolname::text = :role"
                    ),
                    {"role": _TEXT_TO_SQL_ROLE},
                )
                if exists:
                    statement = await connection.scalar(
                        text(
                            "SELECT format("
                            "'ALTER ROLE %I PASSWORD %L', "
                            "CAST(:role AS text), CAST(:password AS text))"
                        ),
                        {
                            "role": _TEXT_TO_SQL_ROLE,
                            "password": _text_to_sql_password(),
                        },
                    )
                else:
                    statement = await connection.scalar(
                        text(
                            "SELECT format("
                            "'CREATE ROLE %I LOGIN PASSWORD %L', "
                            "CAST(:role AS text), CAST(:password AS text))"
                        ),
                        {
                            "role": _TEXT_TO_SQL_ROLE,
                            "password": _text_to_sql_password(),
                        },
                    )
                await connection.exec_driver_sql(statement)
                grant = await connection.scalar(
                    text(
                        "SELECT format("
                        "'GRANT CONNECT ON DATABASE %I TO %I', "
                        "CAST(:database AS text), CAST(:role AS text))"
                    ),
                    {
                        "database": test_database_name,
                        "role": _TEXT_TO_SQL_ROLE,
                    },
                )
                await connection.exec_driver_sql(grant)
        finally:
            await engine.dispose()

    try:
        asyncio.run(run())
    finally:
        if previous is None:
            os.environ.pop("POSTGRES_DB", None)
        else:
            os.environ["POSTGRES_DB"] = previous
        get_settings.cache_clear()
        get_engine.cache_clear()
        get_session_factory.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def migrate_test_database(test_database_name: str) -> None:
    """Apply migrations to the dedicated test database before integration tests."""
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        return

    _ensure_text_to_sql_role(test_database_name)
    environment = os.environ.copy()
    environment["POSTGRES_DB"] = test_database_name
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
    )


@pytest.fixture
async def integration_session(
    monkeypatch: pytest.MonkeyPatch,
    test_database_name: str,
) -> AsyncIterator[AsyncSession]:
    monkeypatch.setenv("POSTGRES_DB", test_database_name)
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    session_factory = get_session_factory()
    async with session_factory() as db_session:
        async with db_session.begin():
            await db_session.execute(
                text(
                    "TRUNCATE TABLE agent_steps, agent_runs, complaints, "
                    "messages, conversations, document_chunks, "
                    "document_sections, documents, order_items, promotions, "
                    "orders, products, categories, customers "
                    "RESTART IDENTITY CASCADE"
                )
            )
        yield db_session

    await get_engine().dispose()
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
