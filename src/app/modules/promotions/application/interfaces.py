from typing import Protocol

from app.modules.promotions.domain.promotion import Promotion


class PromotionRepository(Protocol):
    async def create(self, promotion: Promotion) -> Promotion: ...

    async def get_by_id(self, promotion_id: int) -> Promotion | None: ...

    async def list(
        self,
        *,
        offset: int,
        limit: int,
        product_id: int | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Promotion], int]: ...

    async def update(self, promotion: Promotion) -> Promotion: ...

    async def delete(self, promotion_id: int) -> bool: ...
