from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.modules.products.domain.product import Product
from app.modules.products.domain.product_status import (
    ProductStatus,
)


class ProductResponse(BaseModel):
    product_id: int
    price_brl: float
    name: str
    category_id: int
    description: str | None
    stock_quantity: int
    status: ProductStatus
    specs: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, product: Product) -> "ProductResponse":
        assert product.product_id is not None
        assert product.created_at is not None
        assert product.updated_at is not None
        return cls(
            product_id=product.product_id,
            price_brl=float(product.price_brl),
            name=product.name,
            category_id=product.category_id,
            description=product.description,
            stock_quantity=product.stock_quantity,
            status=product.status,
            specs=product.specs,
            created_at=product.created_at,
            updated_at=product.updated_at,
        )
