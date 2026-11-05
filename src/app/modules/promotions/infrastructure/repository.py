from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.promotions.domain.promotion import Promotion
from app.modules.promotions.infrastructure.models import (
    PromotionModel,
)


class SqlAlchemyPromotionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, promotion: Promotion) -> Promotion:
        async with self._session.begin():
            values = {
                "product_id": promotion.product_id,
                "discount_percent": promotion.discount_percent,
                "description": promotion.description,
                "is_active": promotion.is_active,
                "starts_at": promotion.starts_at,
                "ends_at": promotion.ends_at,
            }
            if promotion.promotion_id is not None:
                values["promotion_id"] = promotion.promotion_id
            model = PromotionModel(**values)
            if promotion.created_at is not None:
                model.created_at = promotion.created_at
            if promotion.updated_at is not None:
                model.updated_at = promotion.updated_at
            self._session.add(model)
            await self._session.flush()
            return model.to_domain()

    async def get_by_id(self, promotion_id: int) -> Promotion | None:
        async with self._session.begin():
            model = await self._session.get(PromotionModel, promotion_id)
            return model.to_domain() if model is not None else None

    async def list(
        self,
        *,
        offset: int,
        limit: int,
        product_id: int | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Promotion], int]:
        async with self._session.begin():
            filters = []
            if product_id is not None:
                filters.append(PromotionModel.product_id == product_id)
            if is_active is not None:
                filters.append(PromotionModel.is_active == is_active)

            total = await self._session.scalar(
                select(func.count())
                .select_from(PromotionModel)
                .where(*filters)
            )
            models = await self._session.scalars(
                select(PromotionModel)
                .where(*filters)
                .order_by(PromotionModel.promotion_id)
                .offset(offset)
                .limit(limit)
            )
            return [model.to_domain() for model in models], int(total or 0)

    async def update(self, promotion: Promotion) -> Promotion:
        async with self._session.begin():
            model = await self._session.get(
                PromotionModel, promotion.promotion_id
            )
            if model is None:
                raise ValueError("Promotion does not exist")
            model.product_id = promotion.product_id
            model.discount_percent = promotion.discount_percent
            model.description = promotion.description
            model.is_active = promotion.is_active
            model.starts_at = promotion.starts_at
            model.ends_at = promotion.ends_at
            await self._session.flush()
            return model.to_domain()

    async def delete(self, promotion_id: int) -> bool:
        async with self._session.begin():
            model = await self._session.get(PromotionModel, promotion_id)
            if model is None:
                return False
            await self._session.delete(model)
            return True
