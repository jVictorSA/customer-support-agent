from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OrderItem:
    product_id: int
    quantity: int
    product_name: str | None = None
