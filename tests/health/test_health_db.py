from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import Settings, get_settings
from app.modules.health.application.check_database_health import (
    CheckDatabaseHealthUseCase,
)
from app.modules.health.domain.health import DatabaseHealthResult
from app.modules.health.presentation.dependencies import (
    get_check_database_health_use_case,
)


class FakeCheckDatabaseHealthUseCase(CheckDatabaseHealthUseCase):
    def __init__(self, result: DatabaseHealthResult) -> None:
        self._result = result

    async def execute(self) -> DatabaseHealthResult:
        return self._result


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


def _override_use_case(result: DatabaseHealthResult) -> None:
    app.dependency_overrides[get_check_database_health_use_case] = (
        lambda: FakeCheckDatabaseHealthUseCase(result)
    )


def test_database_health_is_up(client: TestClient) -> None:
    _override_use_case(DatabaseHealthResult(is_up=True))

    response = client.get("/health/db")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}


def test_database_health_is_down_with_detail_in_development(
    client: TestClient,
) -> None:
    _override_use_case(
        DatabaseHealthResult(is_up=False, detail="RuntimeError: boom")
    )
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_env="development"
    )

    response = client.get("/health/db")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "database": "down",
        "detail": "RuntimeError: boom",
    }


def test_database_health_hides_detail_outside_development(
    client: TestClient,
) -> None:
    _override_use_case(
        DatabaseHealthResult(is_up=False, detail="RuntimeError: boom")
    )
    app.dependency_overrides[get_settings] = lambda: Settings(app_env="prod")

    response = client.get("/health/db")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "down"}
