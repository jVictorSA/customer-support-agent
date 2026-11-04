from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.modules.orders.domain.order_item import OrderItem
from app.modules.orders.domain.order_status import OrderStatus
from app.modules.orders.domain.payment_method import (
    PaymentMethod,
)


@dataclass(frozen=True, slots=True)
class Order:
    order_id: int | None
    customer_id: int
    order_date: datetime
    status: OrderStatus
    total_brl: Decimal
    payment_method: PaymentMethod
    tracking_code: str | None
    estimated_delivery: datetime | None
    notes: str | None
    items: tuple[OrderItem, ...] = ()
    created_at: datetime | None = None
    updated_at: datetime | None = None
