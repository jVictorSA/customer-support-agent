from app.modules.categories.application.exceptions import (
    CategoryNotFoundError,
)
from app.modules.categories.application.interfaces import (
    CategoryRepository,
)
from app.modules.categories.domain.category import Category


class GetCategoryUseCase:
    def __init__(self, repository: CategoryRepository) -> None:
        self._repository = repository

    async def execute(self, category_id: int) -> Category:
        category = await self._repository.get_by_id(category_id)
        if category is None:
            raise CategoryNotFoundError(category_id)
        return category
