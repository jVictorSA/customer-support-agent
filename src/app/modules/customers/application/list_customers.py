from app.modules.customers.application.interfaces import (
    CustomerRepository,
)
from app.modules.customers.domain.customer import Customer


class ListCustomersUseCase:
    def __init__(self, repository: CustomerRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        page: int,
        page_size: int,
        city: str | None = None,
        name: str | None = None,
    ) -> tuple[list[Customer], int]:
        offset = (page - 1) * page_size
        return await self._repository.list(
            offset=offset,
            limit=page_size,
            city=city,
            name=name,
        )
