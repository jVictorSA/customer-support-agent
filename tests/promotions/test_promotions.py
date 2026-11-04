from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.promotions.application.exceptions import (
    PromotionNotFoundError,
)
from app.modules.promotions.application.get_promotion import (
    GetPromotionUseCase,
)
from app.modules.promotions.application.list_promotions import (
    ListPromotionsUseCase,
)
from app.modules.promotions.domain.promotion import Promotion
from app.modules.promotions.presentation.dependencies import (
    get_get_promotion_use_case,
    get_list_promotions_use_case,
)

PROMOTION = Promotion(
    promotion_id=1,
    product_id=102,
    discount_percent=10,
    description="Black Friday",
    is_active=False,
    created_at=datetime(2026, 1, 1, tzinfo=UTC),
    updated_at=datetime(2026, 1, 2, tzinfo=UTC),
)


class FakePromotionRepository:
    def __init__(self, promotion: Promotion | None = PROMOTION) -> None:
        self.promotion = promotion
        self.kwargs: dict[str, object] = {}

    async def list(self, **kwargs: object) -> tuple[list[Promotion], int]:
        self.kwargs = kwargs
        return ([self.promotion] if self.promotion else []), int(
            self.promotion is not None
        )

    async def get_by_id(self, promotion_id: int) -> Promotion | None:
        if (
            self.promotion is None
            or self.promotion.promotion_id != promotion_id
        ):
            return None
        return self.promotion


class FakeListPromotionsUseCase:
    async def execute(self, **kwargs: object) -> tuple[list[Promotion], int]:
        return [PROMOTION], 1


class FakeGetPromotionUseCase:
    async def execute(self, promotion_id: int) -> Promotion:
        if promotion_id != 1:
            raise PromotionNotFoundError(promotion_id)
        return PROMOTION


async def test_list_use_case_forwards_filters() -> None:
    repository = FakePromotionRepository()
    use_case = ListPromotionsUseCase(repository)

    promotions, total = await use_case.execute(
        page=2, page_size=5, product_id=102, is_active=False
    )

    assert promotions == [PROMOTION]
    assert total == 1
    assert repository.kwargs == {
        "offset": 5,
        "limit": 5,
        "product_id": 102,
        "is_active": False,
    }


async def test_get_use_case_raises_when_missing() -> None:
    use_case = GetPromotionUseCase(FakePromotionRepository(promotion=None))

    with pytest.raises(PromotionNotFoundError):
        await use_case.execute(99)


def test_promotions_api_list_and_detail(client: TestClient) -> None:
    app.dependency_overrides[get_list_promotions_use_case] = (
        lambda: FakeListPromotionsUseCase()
    )
    app.dependency_overrides[get_get_promotion_use_case] = (
        lambda: FakeGetPromotionUseCase()
    )

    response = client.get("/promotions?is_active=false")
    detail = client.get("/promotions/1")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["items"][0]["is_active"] is False
    assert detail.status_code == 200
    assert detail.json()["discount_percent"] == 10


def test_promotions_api_not_found(client: TestClient) -> None:
    app.dependency_overrides[get_get_promotion_use_case] = (
        lambda: FakeGetPromotionUseCase()
    )

    response = client.get("/promotions/99")

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["code"] == "promotion_not_found"
