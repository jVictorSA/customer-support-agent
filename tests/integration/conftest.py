import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_engine, get_session_factory

PROJECT_ROOT = Path(__file__).resolve().parents[2]


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


@pytest.fixture(scope="session", autouse=True)
def migrate_test_database(test_database_name: str) -> None:
    """Apply migrations to the dedicated test database before integration tests."""
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        return

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
