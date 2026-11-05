from typing import Protocol
from uuid import UUID

from app.modules.complaints.domain.complaint import Complaint
from app.modules.complaints.domain.complaint_enums import ComplaintStatus


class ComplaintRepository(Protocol):
    async def create(self, complaint: Complaint) -> Complaint: ...

    async def get_open_by_conversation(
        self, conversation_id: int
    ) -> Complaint | None: ...

    async def get_by_public_id(
        self, public_id: UUID, *, customer_id: int
    ) -> Complaint | None: ...

    async def list_by_customer(
        self,
        *,
        customer_id: int,
        offset: int,
        limit: int,
        status: ComplaintStatus | None = None,
    ) -> tuple[list[Complaint], int]: ...


class ConversationHandoff(Protocol):
    async def mark_awaiting_human(self, conversation_id: int) -> None: ...
