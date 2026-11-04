import os

import pytest

from app.core.config import get_settings
from app.db.session import get_engine, get_session_factory
from app.modules.health.infrastructure.repository import (
    SqlAlchemyHealthRepository,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="set RUN_INTEGRATION_TESTS=1 to run integration tests",
    ),
]


async def test_can_connect_to_postgres(
    monkeypatch: pytest.MonkeyPatch,
    test_database_name: str,
) -> None:
    monkeypatch.setenv("POSTGRES_DB", test_database_name)

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    engine = get_engine()
    session_factory = get_session_factory()

    try:
        async with session_factory() as session:
            await SqlAlchemyHealthRepository(session).ping()
    finally:
        await engine.dispose()
        get_settings.cache_clear()
        get_engine.cache_clear()
        get_session_factory.cache_clear()
