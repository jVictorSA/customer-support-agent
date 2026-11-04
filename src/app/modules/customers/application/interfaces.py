from typing import Protocol

from app.modules.customers.domain.customer import Customer


class CustomerRepository(Protocol):
    async def create(self, customer: Customer) -> Customer: ...

    async def get_by_id(self, customer_id: int) -> Customer | None: ...

    async def list(
        self,
        *,
        offset: int,
        limit: int,
        city: str | None = None,
        name: str | None = None,
    ) -> tuple[list[Customer], int]: ...

    async def update(self, customer: Customer) -> Customer: ...

    async def delete(self, customer_id: int) -> bool: ...
