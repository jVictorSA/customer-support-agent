from app.modules.promotions.application.interfaces import (
    PromotionRepository,
)
from app.modules.promotions.domain.promotion import Promotion


class ListPromotionsUseCase:
    def __init__(self, repository: PromotionRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        page: int,
        page_size: int,
        product_id: int | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Promotion], int]:
        offset = (page - 1) * page_size
        return await self._repository.list(
            offset=offset,
            limit=page_size,
            product_id=product_id,
            is_active=is_active,
        )
