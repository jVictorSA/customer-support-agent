from datetime import datetime

from pydantic import BaseModel

from app.modules.customers.domain.customer import Customer


class CustomerResponse(BaseModel):
    customer_id: int
    name: str
    phone: str
    email: str
    city: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, customer: Customer) -> "CustomerResponse":
        assert customer.customer_id is not None
        assert customer.created_at is not None
        assert customer.updated_at is not None
        return cls(
            customer_id=customer.customer_id,
            name=customer.name,
            phone=customer.phone,
            email=customer.email,
            city=customer.city,
            created_at=customer.created_at,
            updated_at=customer.updated_at,
        )
