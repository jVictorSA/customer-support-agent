from datetime import datetime

from pydantic import BaseModel

from app.modules.promotions.domain.promotion import Promotion


class PromotionResponse(BaseModel):
    promotion_id: int
    product_id: int
    discount_percent: int
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, promotion: Promotion) -> "PromotionResponse":
        assert promotion.promotion_id is not None
        assert promotion.created_at is not None
        assert promotion.updated_at is not None
        return cls(
            promotion_id=promotion.promotion_id,
            product_id=promotion.product_id,
            discount_percent=promotion.discount_percent,
            description=promotion.description,
            is_active=promotion.is_active,
            created_at=promotion.created_at,
            updated_at=promotion.updated_at,
        )
