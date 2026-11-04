from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.products.application.exceptions import (
    ProductNotFoundError,
)
from app.modules.products.application.get_product import (
    GetProductUseCase,
)
from app.modules.products.application.list_products import (
    ListProductsUseCase,
)
from app.modules.products.domain.product import Product
from app.modules.products.domain.product_status import (
    ProductStatus,
)
from app.modules.products.presentation.dependencies import (
    get_get_product_use_case,
    get_list_products_use_case,
)

PRODUCT = Product(
    product_id=81,
    price_brl=Decimal("599.90"),
    name="Yamaha C40",
    category_id=5,
    description="Violão clássico",
    stock_quantity=12,
    status=ProductStatus.ACTIVE,
    specs={"top": "Spruce"},
    created_at=datetime(2026, 1, 1, tzinfo=UTC),
    updated_at=datetime(2026, 1, 2, tzinfo=UTC),
)


class FakeProductRepository:
    def __init__(self, product: Product | None = PRODUCT) -> None:
        self.product = product
        self.kwargs: dict[str, object] = {}

    async def list(self, **kwargs: object) -> tuple[list[Product], int]:
        self.kwargs = kwargs
        return ([self.product] if self.product else []), int(
            self.product is not None
        )

    async def get_by_id(self, product_id: int) -> Product | None:
        if self.product is None or self.product.product_id != product_id:
            return None
        return self.product


class FakeListProductsUseCase:
    async def execute(self, **kwargs: object) -> tuple[list[Product], int]:
        return [PRODUCT], 1


class FakeGetProductUseCase:
    async def execute(self, product_id: int) -> Product:
        if product_id != 81:
            raise ProductNotFoundError(product_id)
        return PRODUCT


async def test_list_use_case_forwards_filters() -> None:
    repository = FakeProductRepository()
    use_case = ListProductsUseCase(repository)

    products, total = await use_case.execute(
        page=2,
        page_size=5,
        category_id=5,
        status=ProductStatus.ACTIVE,
        name="yamaha",
        max_price=Decimal("1000"),
    )

    assert products == [PRODUCT]
    assert total == 1
    assert repository.kwargs == {
        "offset": 5,
        "limit": 5,
        "category_id": 5,
        "status": ProductStatus.ACTIVE,
        "name": "yamaha",
        "max_price": Decimal("1000"),
    }


async def test_get_use_case_raises_when_missing() -> None:
    use_case = GetProductUseCase(FakeProductRepository(product=None))

    with pytest.raises(ProductNotFoundError):
        await use_case.execute(999)


def test_products_api_list_and_detail(client: TestClient) -> None:
    app.dependency_overrides[get_list_products_use_case] = (
        lambda: FakeListProductsUseCase()
    )
    app.dependency_overrides[get_get_product_use_case] = (
        lambda: FakeGetProductUseCase()
    )

    response = client.get("/products?page=1&page_size=10")
    detail = client.get("/products/81")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["product_id"] == 81
    assert payload["items"][0]["price_brl"] == 599.9
    assert payload["items"][0]["status"] == "active"
    assert payload["items"][0]["specs"] == {"top": "Spruce"}
    assert detail.status_code == 200
    assert detail.json()["name"] == "Yamaha C40"


def test_products_api_not_found(client: TestClient) -> None:
    app.dependency_overrides[get_get_product_use_case] = (
        lambda: FakeGetProductUseCase()
    )

    response = client.get("/products/999")

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["code"] == "product_not_found"


def test_products_api_validates_max_price(client: TestClient) -> None:
    response = client.get("/products?max_price=-1")

    assert response.status_code == 422
