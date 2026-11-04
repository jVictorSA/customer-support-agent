from fastapi import APIRouter, Depends

from app.modules.categories.application.get_category import (
    GetCategoryUseCase,
)
from app.modules.categories.application.list_categories import (
    ListCategoriesUseCase,
)
from app.modules.categories.presentation.dependencies import (
    get_get_category_use_case,
    get_list_categories_use_case,
)
from app.modules.categories.presentation.schemas import (
    CategoryResponse,
)
from app.presentation.pagination import Page, PaginationParams

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=Page[CategoryResponse])
async def list_categories(
    pagination: PaginationParams = Depends(),
    use_case: ListCategoriesUseCase = Depends(get_list_categories_use_case),
) -> Page[CategoryResponse]:
    categories, total = await use_case.execute(
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return Page(
        items=[CategoryResponse.from_domain(category) for category in categories],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: int,
    use_case: GetCategoryUseCase = Depends(get_get_category_use_case),
) -> CategoryResponse:
    category = await use_case.execute(category_id)
    return CategoryResponse.from_domain(category)
