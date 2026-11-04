from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.products.application.get_product import (
    GetProductUseCase,
)
from app.modules.products.application.list_products import (
    ListProductsUseCase,
)
from app.modules.products.application.interfaces import (
    ProductRepository,
)
from app.modules.products.infrastructure.repository import (
    SqlAlchemyProductRepository,
)


def get_product_repository(
    session: AsyncSession = Depends(get_session),
) -> ProductRepository:
    return SqlAlchemyProductRepository(session)


def get_list_products_use_case(
    repository: ProductRepository = Depends(get_product_repository),
) -> ListProductsUseCase:
    return ListProductsUseCase(repository)


def get_get_product_use_case(
    repository: ProductRepository = Depends(get_product_repository),
) -> GetProductUseCase:
    return GetProductUseCase(repository)
