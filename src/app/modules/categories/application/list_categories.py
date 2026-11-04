from app.modules.categories.application.interfaces import (
    CategoryRepository,
)
from app.modules.categories.domain.category import Category


class ListCategoriesUseCase:
    def __init__(self, repository: CategoryRepository) -> None:
        self._repository = repository

    async def execute(
        self, *, page: int, page_size: int
    ) -> tuple[list[Category], int]:
        offset = (page - 1) * page_size
        return await self._repository.list(offset=offset, limit=page_size)
