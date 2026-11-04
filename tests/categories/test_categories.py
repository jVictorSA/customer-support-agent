from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.categories.application.exceptions import (
    CategoryNotFoundError,
)
from app.modules.categories.application.get_category import (
    GetCategoryUseCase,
)
from app.modules.categories.application.list_categories import (
    ListCategoriesUseCase,
)
from app.modules.categories.domain.category import Category
from app.modules.categories.presentation.dependencies import (
    get_get_category_use_case,
    get_list_categories_use_case,
)

CATEGORY = Category(
    category_id=1,
    name="Guitarras",
    description="Guitarras elétricas",
    created_at=datetime(2026, 1, 1, tzinfo=UTC),
    updated_at=datetime(2026, 1, 2, tzinfo=UTC),
)


class FakeCategoryRepository:
    def __init__(self, category: Category | None = CATEGORY) -> None:
        self.category = category
        self.offset: int | None = None
        self.limit: int | None = None

    async def list(
        self, *, offset: int, limit: int
    ) -> tuple[list[Category], int]:
        self.offset = offset
        self.limit = limit
        return ([self.category] if self.category else []), int(
            self.category is not None
        )

    async def get_by_id(self, category_id: int) -> Category | None:
        if self.category is None or self.category.category_id != category_id:
            return None
        return self.category


class FakeListCategoriesUseCase:
    async def execute(
        self, *, page: int, page_size: int
    ) -> tuple[list[Category], int]:
        return [CATEGORY], 1


class FakeGetCategoryUseCase:
    async def execute(self, category_id: int) -> Category:
        if category_id != 1:
            raise CategoryNotFoundError(category_id)
        return CATEGORY


async def test_list_use_case_computes_offset() -> None:
    repository = FakeCategoryRepository()
    use_case = ListCategoriesUseCase(repository)

    categories, total = await use_case.execute(page=3, page_size=10)

    assert categories == [CATEGORY]
    assert total == 1
    assert repository.offset == 20
    assert repository.limit == 10


async def test_get_use_case_raises_when_missing() -> None:
    use_case = GetCategoryUseCase(FakeCategoryRepository(category=None))

    with pytest.raises(CategoryNotFoundError):
        await use_case.execute(99)


def test_categories_api_list_and_detail(client: TestClient) -> None:
    app.dependency_overrides[get_list_categories_use_case] = (
        lambda: FakeListCategoriesUseCase()
    )
    app.dependency_overrides[get_get_category_use_case] = (
        lambda: FakeGetCategoryUseCase()
    )

    response = client.get("/categories?page=1&page_size=10")
    detail = client.get("/categories/1")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "category_id": 1,
                "name": "Guitarras",
                "description": "Guitarras elétricas",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-02T00:00:00Z",
            }
        ],
        "total": 1,
        "page": 1,
        "page_size": 10,
    }
    assert detail.status_code == 200
    assert detail.json()["category_id"] == 1


def test_categories_api_not_found(client: TestClient) -> None:
    app.dependency_overrides[get_get_category_use_case] = (
        lambda: FakeGetCategoryUseCase()
    )

    response = client.get("/categories/99")

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "code": "category_not_found",
        "message": "Category 99 not found",
    }


def test_categories_api_rejects_invalid_page_size(client: TestClient) -> None:
    response = client.get("/categories?page_size=101")

    assert response.status_code == 422
