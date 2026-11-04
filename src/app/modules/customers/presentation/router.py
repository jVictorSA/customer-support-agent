from fastapi import APIRouter, Depends, Query

from app.modules.customers.application.get_customer import (
    GetCustomerUseCase,
)
from app.modules.customers.application.list_customers import (
    ListCustomersUseCase,
)
from app.modules.customers.presentation.dependencies import (
    get_get_customer_use_case,
    get_list_customers_use_case,
)
from app.modules.customers.presentation.schemas import (
    CustomerResponse,
)
from app.presentation.pagination import Page, PaginationParams

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("", response_model=Page[CustomerResponse])
async def list_customers(
    pagination: PaginationParams = Depends(),
    city: str | None = Query(None, min_length=1),
    name: str | None = Query(None, min_length=1),
    use_case: ListCustomersUseCase = Depends(get_list_customers_use_case),
) -> Page[CustomerResponse]:
    customers, total = await use_case.execute(
        page=pagination.page,
        page_size=pagination.page_size,
        city=city,
        name=name,
    )
    return Page(
        items=[CustomerResponse.from_domain(customer) for customer in customers],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: int,
    use_case: GetCustomerUseCase = Depends(get_get_customer_use_case),
) -> CustomerResponse:
    customer = await use_case.execute(customer_id)
    return CustomerResponse.from_domain(customer)
