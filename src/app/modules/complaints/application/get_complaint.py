from uuid import UUID

from app.modules.complaints.application.exceptions import (
    ComplaintNotFoundError,
)
from app.modules.complaints.application.interfaces import (
    ComplaintRepository,
)
from app.modules.complaints.domain.complaint import Complaint


class GetComplaintUseCase:
    def __init__(self, repository: ComplaintRepository) -> None:
        self._repository = repository

    async def execute(
        self, public_id: UUID, *, customer_id: int
    ) -> Complaint:
        complaint = await self._repository.get_by_public_id(
            public_id, customer_id=customer_id
        )
        if complaint is None:
            raise ComplaintNotFoundError()
        return complaint
