from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OrderItem:
    product_id: int
    quantity: int
    product_name: str | None = None
    is_final_sale: bool = False
    is_customized: bool = False
    is_hygiene_restricted: bool = False
