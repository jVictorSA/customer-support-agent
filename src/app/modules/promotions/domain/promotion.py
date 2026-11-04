from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Promotion:
    promotion_id: int | None
    product_id: int
    discount_percent: int
    description: str | None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
