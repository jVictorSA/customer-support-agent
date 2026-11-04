from typing import Protocol

from app.modules.categories.domain.category import Category


class CategoryRepository(Protocol):
    async def create(self, category: Category) -> Category: ...

    async def get_by_id(self, category_id: int) -> Category | None: ...

    async def list(
        self,
        *,
        offset: int,
        limit: int,
    ) -> tuple[list[Category], int]: ...

    async def update(self, category: Category) -> Category: ...

    async def delete(self, category_id: int) -> bool: ...
