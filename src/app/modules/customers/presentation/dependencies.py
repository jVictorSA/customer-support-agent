from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.customers.application.get_customer import (
    GetCustomerUseCase,
)
from app.modules.customers.application.list_customers import (
    ListCustomersUseCase,
)
from app.modules.customers.application.interfaces import (
    CustomerRepository,
)
from app.modules.customers.infrastructure.repository import (
    SqlAlchemyCustomerRepository,
)


def get_customer_repository(
    session: AsyncSession = Depends(get_session),
) -> CustomerRepository:
    return SqlAlchemyCustomerRepository(session)


def get_list_customers_use_case(
    repository: CustomerRepository = Depends(get_customer_repository),
) -> ListCustomersUseCase:
    return ListCustomersUseCase(repository)


def get_get_customer_use_case(
    repository: CustomerRepository = Depends(get_customer_repository),
) -> GetCustomerUseCase:
    return GetCustomerUseCase(repository)
