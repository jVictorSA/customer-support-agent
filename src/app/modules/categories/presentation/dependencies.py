from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.categories.application.get_category import (
    GetCategoryUseCase,
)
from app.modules.categories.application.list_categories import (
    ListCategoriesUseCase,
)
from app.modules.categories.application.interfaces import (
    CategoryRepository,
)
from app.modules.categories.infrastructure.repository import (
    SqlAlchemyCategoryRepository,
)


def get_category_repository(
    session: AsyncSession = Depends(get_session),
) -> CategoryRepository:
    return SqlAlchemyCategoryRepository(session)


def get_list_categories_use_case(
    repository: CategoryRepository = Depends(get_category_repository),
) -> ListCategoriesUseCase:
    return ListCategoriesUseCase(repository)


def get_get_category_use_case(
    repository: CategoryRepository = Depends(get_category_repository),
) -> GetCategoryUseCase:
    return GetCategoryUseCase(repository)
