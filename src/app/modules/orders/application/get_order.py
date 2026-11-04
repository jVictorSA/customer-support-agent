from app.modules.orders.application.exceptions import (
    OrderNotFoundError,
)
from app.modules.orders.application.interfaces import (
    OrderRepository,
)
from app.modules.orders.domain.order import Order


class GetOrderUseCase:
    def __init__(self, repository: OrderRepository) -> None:
        self._repository = repository

    async def execute(self, order_id: int) -> Order:
        order = await self._repository.get_by_id(order_id)
        if order is None:
            raise OrderNotFoundError(order_id)
        return order
