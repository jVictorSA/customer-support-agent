from app.core.exceptions import NotFoundError


class PromotionNotFoundError(NotFoundError):
    code = "promotion_not_found"
    message = "Promotion not found"

    def __init__(self, promotion_id: int) -> None:
        super().__init__(f"Promotion {promotion_id} not found")
