from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.modules.products.domain.product_status import (
    ProductStatus,
)


@dataclass(frozen=True, slots=True)
class Product:
    product_id: int | None
    price_brl: Decimal
    name: str
    category_id: int
    description: str | None
    stock_quantity: int
    status: ProductStatus
    specs: dict[str, Any]
    created_at: datetime | None = None
    updated_at: datetime | None = None
