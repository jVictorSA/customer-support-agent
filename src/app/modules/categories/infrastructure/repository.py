from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.categories.domain.category import Category
from app.modules.categories.infrastructure.models import (
    CategoryModel,
)


class SqlAlchemyCategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, category: Category) -> Category:
        async with self._session.begin():
            values = {
                "name": category.name,
                "description": category.description,
            }
            if category.category_id is not None:
                values["category_id"] = category.category_id
            model = CategoryModel(**values)
            self._apply_timestamps(model, category)
            self._session.add(model)
            await self._session.flush()
            return model.to_domain()

    async def get_by_id(self, category_id: int) -> Category | None:
        async with self._session.begin():
            model = await self._session.get(CategoryModel, category_id)
            return model.to_domain() if model is not None else None

    async def list(
        self,
        *,
        offset: int,
        limit: int,
    ) -> tuple[list[Category], int]:
        async with self._session.begin():
            total = await self._session.scalar(
                select(func.count()).select_from(CategoryModel)
            )
            models = await self._session.scalars(
                select(CategoryModel)
                .order_by(CategoryModel.name, CategoryModel.category_id)
                .offset(offset)
                .limit(limit)
            )
            return [model.to_domain() for model in models], int(total or 0)

    async def update(self, category: Category) -> Category:
        async with self._session.begin():
            model = await self._session.get(CategoryModel, category.category_id)
            if model is None:
                raise ValueError("Category does not exist")
            model.name = category.name
            model.description = category.description
            await self._session.flush()
            return model.to_domain()

    async def delete(self, category_id: int) -> bool:
        async with self._session.begin():
            model = await self._session.get(CategoryModel, category_id)
            if model is None:
                return False
            await self._session.delete(model)
            return True

    @staticmethod
    def _apply_timestamps(model: CategoryModel, category: Category) -> None:
        if category.created_at is not None:
            model.created_at = category.created_at
        if category.updated_at is not None:
            model.updated_at = category.updated_at
