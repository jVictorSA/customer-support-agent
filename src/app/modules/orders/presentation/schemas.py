from datetime import datetime

from pydantic import BaseModel

from app.modules.orders.domain.order import Order
from app.modules.orders.domain.order_item import OrderItem
from app.modules.orders.domain.order_status import OrderStatus
from app.modules.orders.domain.payment_method import (
    PaymentMethod,
)
from app.modules.orders.domain.sales_channel import SalesChannel


class OrderItemResponse(BaseModel):
    product_id: int
    quantity: int
    product_name: str | None
    is_final_sale: bool
    is_customized: bool
    is_hygiene_restricted: bool

    @classmethod
    def from_domain(cls, item: OrderItem) -> "OrderItemResponse":
        return cls(
            product_id=item.product_id,
            quantity=item.quantity,
            product_name=item.product_name,
            is_final_sale=item.is_final_sale,
            is_customized=item.is_customized,
            is_hygiene_restricted=item.is_hygiene_restricted,
        )


class OrderSummaryResponse(BaseModel):
    order_id: int
    customer_id: int
    order_date: datetime
    status: OrderStatus
    total_brl: float
    payment_method: PaymentMethod
    sales_channel: SalesChannel | None
    tracking_code: str | None
    estimated_delivery: datetime | None
    delivered_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, order: Order) -> "OrderSummaryResponse":
        assert order.order_id is not None
        assert order.created_at is not None
        assert order.updated_at is not None
        return cls(
            order_id=order.order_id,
            customer_id=order.customer_id,
            order_date=order.order_date,
            status=order.status,
            total_brl=float(order.total_brl),
            payment_method=order.payment_method,
            sales_channel=order.sales_channel,
            tracking_code=order.tracking_code,
            estimated_delivery=order.estimated_delivery,
            delivered_at=order.delivered_at,
            notes=order.notes,
            created_at=order.created_at,
            updated_at=order.updated_at,
        )


class OrderDetailResponse(OrderSummaryResponse):
    items: list[OrderItemResponse]

    @classmethod
    def from_domain(cls, order: Order) -> "OrderDetailResponse":
        summary = OrderSummaryResponse.from_domain(order)
        return cls(
            **summary.model_dump(),
            items=[
                OrderItemResponse.from_domain(item) for item in order.items
            ],
        )
