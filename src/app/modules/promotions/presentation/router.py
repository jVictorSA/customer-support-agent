from fastapi import APIRouter, Depends, Query

from app.modules.promotions.application.get_promotion import (
    GetPromotionUseCase,
)
from app.modules.promotions.application.list_promotions import (
    ListPromotionsUseCase,
)
from app.modules.promotions.presentation.dependencies import (
    get_get_promotion_use_case,
    get_list_promotions_use_case,
)
from app.modules.promotions.presentation.schemas import (
    PromotionResponse,
)
from app.presentation.pagination import Page, PaginationParams

router = APIRouter(prefix="/promotions", tags=["Promotions"])


@router.get("", response_model=Page[PromotionResponse])
async def list_promotions(
    pagination: PaginationParams = Depends(),
    product_id: int | None = Query(None),
    is_active: bool | None = Query(None),
    use_case: ListPromotionsUseCase = Depends(get_list_promotions_use_case),
) -> Page[PromotionResponse]:
    promotions, total = await use_case.execute(
        page=pagination.page,
        page_size=pagination.page_size,
        product_id=product_id,
        is_active=is_active,
    )
    return Page(
        items=[
            PromotionResponse.from_domain(promotion) for promotion in promotions
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{promotion_id}", response_model=PromotionResponse)
async def get_promotion(
    promotion_id: int,
    use_case: GetPromotionUseCase = Depends(get_get_promotion_use_case),
) -> PromotionResponse:
    promotion = await use_case.execute(promotion_id)
    return PromotionResponse.from_domain(promotion)
