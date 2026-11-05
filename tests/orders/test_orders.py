from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.orders.application.exceptions import (
    OrderNotFoundError,
)
from app.modules.orders.application.get_order import (
    GetOrderUseCase,
)
from app.modules.orders.application.list_orders import (
    ListOrdersUseCase,
)
from app.modules.orders.domain.order import Order
from app.modules.orders.domain.order_item import OrderItem
from app.modules.orders.domain.order_status import OrderStatus
from app.modules.orders.domain.payment_method import (
    PaymentMethod,
)
from app.modules.orders.presentation.dependencies import (
    get_get_order_use_case,
    get_list_orders_use_case,
)

ORDER = Order(
    order_id=1,
    customer_id=3,
    order_date=datetime(2025, 10, 15, tzinfo=UTC),
    status=OrderStatus.DELIVERED,
    total_brl=Decimal("11499.00"),
    payment_method=PaymentMethod.PIX,
    tracking_code="BRAB1234567BR",
    estimated_delivery=datetime(2025, 10, 25, tzinfo=UTC),
    notes=None,
    items=(OrderItem(product_id=93, quantity=1, product_name="Martin D-28"),),
    created_at=datetime(2026, 1, 1, tzinfo=UTC),
    updated_at=datetime(2026, 1, 2, tzinfo=UTC),
)


class FakeOrderRepository:
    def __init__(self, order: Order | None = ORDER) -> None:
        self.order = order
        self.kwargs: dict[str, object] = {}

    async def list(self, **kwargs: object) -> tuple[list[Order], int]:
        self.kwargs = kwargs
        return ([self.order] if self.order else []), int(
            self.order is not None
        )

    async def get_by_id(self, order_id: int) -> Order | None:
        if self.order is None or self.order.order_id != order_id:
            return None
        return self.order


class FakeListOrdersUseCase:
    async def execute(self, **kwargs: object) -> tuple[list[Order], int]:
        return [ORDER], 1


class FakeGetOrderUseCase:
    async def execute(self, order_id: int) -> Order:
        if order_id != 1:
            raise OrderNotFoundError(order_id)
        return ORDER


async def test_list_use_case_forwards_filters() -> None:
    repository = FakeOrderRepository()
    use_case = ListOrdersUseCase(repository)

    orders, total = await use_case.execute(
        page=2, page_size=5, customer_id=3, status=OrderStatus.DELIVERED
    )

    assert orders == [ORDER]
    assert total == 1
    assert repository.kwargs == {
        "offset": 5,
        "limit": 5,
        "customer_id": 3,
        "status": OrderStatus.DELIVERED,
    }


async def test_get_use_case_raises_when_missing() -> None:
    use_case = GetOrderUseCase(FakeOrderRepository(order=None))

    with pytest.raises(OrderNotFoundError):
        await use_case.execute(99)


def test_orders_api_list_and_detail(client: TestClient) -> None:
    app.dependency_overrides[get_list_orders_use_case] = (
        lambda: FakeListOrdersUseCase()
    )
    app.dependency_overrides[get_get_order_use_case] = (
        lambda: FakeGetOrderUseCase()
    )

    response = client.get("/orders?customer_id=3")
    detail = client.get("/orders/1")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert "items" not in payload["items"][0]
    assert detail.status_code == 200
    assert detail.json()["items"] == [
        {
            "product_id": 93,
            "quantity": 1,
            "product_name": "Martin D-28",
            "is_final_sale": False,
            "is_customized": False,
            "is_hygiene_restricted": False,
        }
    ]


def test_orders_api_not_found(client: TestClient) -> None:
    app.dependency_overrides[get_get_order_use_case] = (
        lambda: FakeGetOrderUseCase()
    )

    response = client.get("/orders/99")

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["code"] == "order_not_found"
