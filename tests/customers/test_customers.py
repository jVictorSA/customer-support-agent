from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.customers.application.exceptions import (
    CustomerNotFoundError,
)
from app.modules.customers.application.get_customer import (
    GetCustomerUseCase,
)
from app.modules.customers.application.list_customers import (
    ListCustomersUseCase,
)
from app.modules.customers.domain.customer import Customer
from app.modules.customers.presentation.dependencies import (
    get_get_customer_use_case,
    get_list_customers_use_case,
)

CUSTOMER = Customer(
    customer_id=1,
    name="Lucas Mendes",
    phone="(67) 99812-3456",
    email="lucas@example.com",
    city="Campo Grande",
    created_at=datetime(2026, 1, 1, tzinfo=UTC),
    updated_at=datetime(2026, 1, 2, tzinfo=UTC),
)


class FakeCustomerRepository:
    def __init__(self, customer: Customer | None = CUSTOMER) -> None:
        self.customer = customer
        self.kwargs: dict[str, object] = {}

    async def list(self, **kwargs: object) -> tuple[list[Customer], int]:
        self.kwargs = kwargs
        return ([self.customer] if self.customer else []), int(
            self.customer is not None
        )

    async def get_by_id(self, customer_id: int) -> Customer | None:
        if self.customer is None or self.customer.customer_id != customer_id:
            return None
        return self.customer


class FakeListCustomersUseCase:
    async def execute(self, **kwargs: object) -> tuple[list[Customer], int]:
        return [CUSTOMER], 1


class FakeGetCustomerUseCase:
    async def execute(self, customer_id: int) -> Customer:
        if customer_id != 1:
            raise CustomerNotFoundError(customer_id)
        return CUSTOMER


async def test_list_use_case_forwards_filters() -> None:
    repository = FakeCustomerRepository()
    use_case = ListCustomersUseCase(repository)

    customers, total = await use_case.execute(
        page=1, page_size=20, city="Campo Grande", name="Lucas"
    )

    assert customers == [CUSTOMER]
    assert total == 1
    assert repository.kwargs == {
        "offset": 0,
        "limit": 20,
        "city": "Campo Grande",
        "name": "Lucas",
    }


async def test_get_use_case_raises_when_missing() -> None:
    use_case = GetCustomerUseCase(FakeCustomerRepository(customer=None))

    with pytest.raises(CustomerNotFoundError):
        await use_case.execute(99)


def test_customers_api_list_and_detail(client: TestClient) -> None:
    app.dependency_overrides[get_list_customers_use_case] = (
        lambda: FakeListCustomersUseCase()
    )
    app.dependency_overrides[get_get_customer_use_case] = (
        lambda: FakeGetCustomerUseCase()
    )

    response = client.get("/customers?city=Campo%20Grande")
    detail = client.get("/customers/1")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["items"][0]["city"] == "Campo Grande"
    assert detail.status_code == 200
    assert detail.json()["email"] == "lucas@example.com"


def test_customers_api_not_found(client: TestClient) -> None:
    app.dependency_overrides[get_get_customer_use_case] = (
        lambda: FakeGetCustomerUseCase()
    )

    response = client.get("/customers/99")

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["code"] == "customer_not_found"
