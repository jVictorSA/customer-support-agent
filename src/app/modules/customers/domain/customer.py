from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Customer:
    customer_id: int | None
    name: str
    phone: str
    email: str
    city: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
