from decimal import Decimal

from fastapi import APIRouter, Depends, Query

from app.modules.products.application.get_product import (
    GetProductUseCase,
)
from app.modules.products.application.list_products import (
    ListProductsUseCase,
)
from app.modules.products.domain.product_status import (
    ProductStatus,
)
from app.modules.products.presentation.dependencies import (
    get_get_product_use_case,
    get_list_products_use_case,
)
from app.modules.products.presentation.schemas import (
    ProductResponse,
)
from app.presentation.pagination import Page, PaginationParams

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=Page[ProductResponse])
async def list_products(
    pagination: PaginationParams = Depends(),
    category_id: int | None = Query(None),
    status: ProductStatus | None = Query(None),
    name: str | None = Query(None, min_length=1),
    max_price: Decimal | None = Query(None, ge=0),
    use_case: ListProductsUseCase = Depends(get_list_products_use_case),
) -> Page[ProductResponse]:
    products, total = await use_case.execute(
        page=pagination.page,
        page_size=pagination.page_size,
        category_id=category_id,
        status=status,
        name=name,
        max_price=max_price,
    )
    return Page(
        items=[ProductResponse.from_domain(product) for product in products],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    use_case: GetProductUseCase = Depends(get_get_product_use_case),
) -> ProductResponse:
    product = await use_case.execute(product_id)
    return ProductResponse.from_domain(product)
