from app.modules.auth.domain.identity import CustomerIdentity
from app.modules.customers.application.interfaces import CustomerRepository


class RepositoryCustomerDirectory:
    """Expose customer lookups to auth without leaking the customers module."""

    def __init__(self, repository: CustomerRepository) -> None:
        self._repository = repository

    async def find_by_credentials(
        self, *, email: str, phone: str
    ) -> CustomerIdentity | None:
        customer = await self._repository.find_by_credentials(
            email=email, phone=phone
        )
        return _to_identity(customer) if customer is not None else None

    async def get_by_id(self, customer_id: int) -> CustomerIdentity | None:
        customer = await self._repository.get_by_id(customer_id)
        return _to_identity(customer) if customer is not None else None


def _to_identity(customer) -> CustomerIdentity:
    assert customer.customer_id is not None
    return CustomerIdentity(
        customer_id=customer.customer_id,
        name=customer.name,
        email=customer.email,
        phone=customer.phone,
        city=customer.city,
    )
