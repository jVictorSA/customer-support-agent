from app.modules.promotions.application.exceptions import (
    PromotionNotFoundError,
)
from app.modules.promotions.application.interfaces import (
    PromotionRepository,
)
from app.modules.promotions.domain.promotion import Promotion


class GetPromotionUseCase:
    def __init__(self, repository: PromotionRepository) -> None:
        self._repository = repository

    async def execute(self, promotion_id: int) -> Promotion:
        promotion = await self._repository.get_by_id(promotion_id)
        if promotion is None:
            raise PromotionNotFoundError(promotion_id)
        return promotion
