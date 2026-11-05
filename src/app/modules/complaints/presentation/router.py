from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.modules.auth.domain.identity import CustomerIdentity
from app.modules.auth.presentation.dependencies import get_current_identity
from app.modules.complaints.application.get_complaint import (
    GetComplaintUseCase,
)
from app.modules.complaints.application.list_complaints import (
    ListComplaintsUseCase,
)
from app.modules.complaints.domain.complaint_enums import ComplaintStatus
from app.modules.complaints.presentation.dependencies import (
    get_get_complaint_use_case,
    get_list_complaints_use_case,
)
from app.modules.complaints.presentation.schemas import ComplaintResponse
from app.presentation.pagination import Page, PaginationParams

router = APIRouter(prefix="/complaints", tags=["Complaints"])


@router.get("", response_model=Page[ComplaintResponse])
async def list_complaints(
    pagination: PaginationParams = Depends(),
    status: ComplaintStatus | None = Query(None),
    customer: CustomerIdentity = Depends(get_current_identity),
    use_case: ListComplaintsUseCase = Depends(
        get_list_complaints_use_case
    ),
) -> Page[ComplaintResponse]:
    complaints, total = await use_case.execute(
        customer_id=customer.customer_id,
        page=pagination.page,
        page_size=pagination.page_size,
        status=status,
    )
    return Page(
        items=[
            ComplaintResponse.from_domain(complaint)
            for complaint in complaints
        ],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{public_id}", response_model=ComplaintResponse)
async def get_complaint(
    public_id: UUID,
    customer: CustomerIdentity = Depends(get_current_identity),
    use_case: GetComplaintUseCase = Depends(get_get_complaint_use_case),
) -> ComplaintResponse:
    complaint = await use_case.execute(
        public_id, customer_id=customer.customer_id
    )
    return ComplaintResponse.from_domain(complaint)
