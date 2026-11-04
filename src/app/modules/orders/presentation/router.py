from fastapi import APIRouter, Depends, Query

from app.modules.orders.application.get_order import (
    GetOrderUseCase,
)
from app.modules.orders.application.list_orders import (
    ListOrdersUseCase,
)
from app.modules.orders.domain.order_status import OrderStatus
from app.modules.orders.presentation.dependencies import (
    get_get_order_use_case,
    get_list_orders_use_case,
)
from app.modules.orders.presentation.schemas import (
    OrderDetailResponse,
    OrderSummaryResponse,
)
from app.presentation.pagination import Page, PaginationParams

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.get("", response_model=Page[OrderSummaryResponse])
async def list_orders(
    pagination: PaginationParams = Depends(),
    customer_id: int | None = Query(None),
    status: OrderStatus | None = Query(None),
    use_case: ListOrdersUseCase = Depends(get_list_orders_use_case),
) -> Page[OrderSummaryResponse]:
    orders, total = await use_case.execute(
        page=pagination.page,
        page_size=pagination.page_size,
        customer_id=customer_id,
        status=status,
    )
    return Page(
        items=[OrderSummaryResponse.from_domain(order) for order in orders],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{order_id}", response_model=OrderDetailResponse)
async def get_order(
    order_id: int,
    use_case: GetOrderUseCase = Depends(get_get_order_use_case),
) -> OrderDetailResponse:
    order = await use_case.execute(order_id)
    return OrderDetailResponse.from_domain(order)
