from decimal import Decimal

from app.modules.products.application.interfaces import (
    ProductRepository,
)
from app.modules.products.domain.product import Product
from app.modules.products.domain.product_status import (
    ProductStatus,
)


class ListProductsUseCase:
    def __init__(self, repository: ProductRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        page: int,
        page_size: int,
        category_id: int | None = None,
        status: ProductStatus | None = None,
        name: str | None = None,
        max_price: Decimal | None = None,
    ) -> tuple[list[Product], int]:
        offset = (page - 1) * page_size
        return await self._repository.list(
            offset=offset,
            limit=page_size,
            category_id=category_id,
            status=status,
            name=name,
            max_price=max_price,
        )
