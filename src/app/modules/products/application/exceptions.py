from app.core.exceptions import NotFoundError


class ProductNotFoundError(NotFoundError):
    code = "product_not_found"
    message = "Product not found"

    def __init__(self, product_id: int) -> None:
        super().__init__(f"Product {product_id} not found")
