from app.modules.complaints.application.interfaces import (
    ComplaintRepository,
)
from app.modules.complaints.domain.complaint import Complaint
from app.modules.complaints.domain.complaint_enums import ComplaintStatus


class ListComplaintsUseCase:
    def __init__(self, repository: ComplaintRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        customer_id: int,
        page: int,
        page_size: int,
        status: ComplaintStatus | None = None,
    ) -> tuple[list[Complaint], int]:
        return await self._repository.list_by_customer(
            customer_id=customer_id,
            offset=(page - 1) * page_size,
            limit=page_size,
            status=status,
        )
