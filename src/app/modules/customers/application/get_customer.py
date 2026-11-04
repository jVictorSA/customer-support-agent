from app.modules.customers.application.exceptions import (
    CustomerNotFoundError,
)
from app.modules.customers.application.interfaces import (
    CustomerRepository,
)
from app.modules.customers.domain.customer import Customer


class GetCustomerUseCase:
    def __init__(self, repository: CustomerRepository) -> None:
        self._repository = repository

    async def execute(self, customer_id: int) -> Customer:
        customer = await self._repository.get_by_id(customer_id)
        if customer is None:
            raise CustomerNotFoundError(customer_id)
        return customer
