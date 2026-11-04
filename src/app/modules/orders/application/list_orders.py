from app.modules.orders.application.interfaces import (
    OrderRepository,
)
from app.modules.orders.domain.order import Order
from app.modules.orders.domain.order_status import OrderStatus


class ListOrdersUseCase:
    def __init__(self, repository: OrderRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        page: int,
        page_size: int,
        customer_id: int | None = None,
        status: OrderStatus | None = None,
    ) -> tuple[list[Order], int]:
        offset = (page - 1) * page_size
        return await self._repository.list(
            offset=offset,
            limit=page_size,
            customer_id=customer_id,
            status=status,
        )
