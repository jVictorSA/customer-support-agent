from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.orders.application.get_order import (
    GetOrderUseCase,
)
from app.modules.orders.application.list_orders import (
    ListOrdersUseCase,
)
from app.modules.orders.application.interfaces import (
    OrderRepository,
)
from app.modules.orders.infrastructure.repository import (
    SqlAlchemyOrderRepository,
)


def get_order_repository(
    session: AsyncSession = Depends(get_session),
) -> OrderRepository:
    return SqlAlchemyOrderRepository(session)


def get_list_orders_use_case(
    repository: OrderRepository = Depends(get_order_repository),
) -> ListOrdersUseCase:
    return ListOrdersUseCase(repository)


def get_get_order_use_case(
    repository: OrderRepository = Depends(get_order_repository),
) -> GetOrderUseCase:
    return GetOrderUseCase(repository)
