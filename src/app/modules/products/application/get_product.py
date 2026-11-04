from app.modules.products.application.exceptions import (
    ProductNotFoundError,
)
from app.modules.products.application.interfaces import (
    ProductRepository,
)
from app.modules.products.domain.product import Product


class GetProductUseCase:
    def __init__(self, repository: ProductRepository) -> None:
        self._repository = repository

    async def execute(self, product_id: int) -> Product:
        product = await self._repository.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundError(product_id)
        return product
