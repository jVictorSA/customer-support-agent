from decimal import Decimal
from typing import Protocol

from app.modules.products.domain.product import Product
from app.modules.products.domain.product_status import (
    ProductStatus,
)


class ProductRepository(Protocol):
    async def create(self, product: Product) -> Product: ...

    async def get_by_id(self, product_id: int) -> Product | None: ...

    async def list(
        self,
        *,
        offset: int,
        limit: int,
        category_id: int | None = None,
        status: ProductStatus | None = None,
        name: str | None = None,
        max_price: Decimal | None = None,
    ) -> tuple[list[Product], int]: ...

    async def update(self, product: Product) -> Product: ...

    async def delete(self, product_id: int) -> bool: ...
