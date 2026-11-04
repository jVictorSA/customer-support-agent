from typing import Protocol

from app.modules.orders.domain.order import Order
from app.modules.orders.domain.order_status import OrderStatus


class OrderRepository(Protocol):
    async def create(self, order: Order) -> Order: ...

    async def get_by_id(self, order_id: int) -> Order | None: ...

    async def list(
        self,
        *,
        offset: int,
        limit: int,
        customer_id: int | None = None,
        status: OrderStatus | None = None,
    ) -> tuple[list[Order], int]: ...

    async def update(self, order: Order) -> Order: ...

    async def delete(self, order_id: int) -> bool: ...
