from app.core.exceptions import NotFoundError


class OrderNotFoundError(NotFoundError):
    code = "order_not_found"
    message = "Order not found"

    def __init__(self, order_id: int) -> None:
        super().__init__(f"Order {order_id} not found")
