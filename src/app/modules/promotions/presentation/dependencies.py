from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.promotions.application.get_promotion import (
    GetPromotionUseCase,
)
from app.modules.promotions.application.list_promotions import (
    ListPromotionsUseCase,
)
from app.modules.promotions.application.interfaces import (
    PromotionRepository,
)
from app.modules.promotions.infrastructure.repository import (
    SqlAlchemyPromotionRepository,
)


def get_promotion_repository(
    session: AsyncSession = Depends(get_session),
) -> PromotionRepository:
    return SqlAlchemyPromotionRepository(session)


def get_list_promotions_use_case(
    repository: PromotionRepository = Depends(get_promotion_repository),
) -> ListPromotionsUseCase:
    return ListPromotionsUseCase(repository)


def get_get_promotion_use_case(
    repository: PromotionRepository = Depends(get_promotion_repository),
) -> GetPromotionUseCase:
    return GetPromotionUseCase(repository)
