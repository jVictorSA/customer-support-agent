from app.core.exceptions import NotFoundError


class CustomerNotFoundError(NotFoundError):
    code = "customer_not_found"
    message = "Customer not found"

    def __init__(self, customer_id: int) -> None:
        super().__init__(f"Customer {customer_id} not found")
