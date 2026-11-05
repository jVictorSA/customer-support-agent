import logging
from uuid import uuid4

from app.modules.complaints.application.interfaces import (
    ComplaintRepository,
    ConversationHandoff,
)
from app.modules.complaints.domain.complaint import Complaint
from app.modules.complaints.domain.complaint_enums import (
    ComplaintCategory,
    ComplaintPriority,
)
from app.modules.complaints.domain.result import RegisterComplaintResult

logger = logging.getLogger(__name__)


class RegisterComplaintUseCase:
    def __init__(
        self,
        *,
        repository: ComplaintRepository,
        handoff: ConversationHandoff,
    ) -> None:
        self._repository = repository
        self._handoff = handoff

    async def execute(
        self,
        *,
        conversation_id: int,
        customer_id: int,
        message_id: int | None,
        order_id: int | None,
        category: ComplaintCategory,
        description: str,
        priority: ComplaintPriority = ComplaintPriority.NORMAL,
    ) -> RegisterComplaintResult:
        existing = await self._repository.get_open_by_conversation(
            conversation_id
        )
        if existing is not None:
            await self._mark_handoff(conversation_id)
            return RegisterComplaintResult(
                complaint=existing, already_open=True
            )

        complaint = await self._repository.create(
            Complaint(
                complaint_id=None,
                public_id=uuid4(),
                conversation_id=conversation_id,
                customer_id=customer_id,
                message_id=message_id,
                order_id=order_id,
                category=category,
                description=description.strip(),
                priority=priority,
            )
        )
        await self._mark_handoff(conversation_id)
        return RegisterComplaintResult(
            complaint=complaint, already_open=False
        )

    async def _mark_handoff(self, conversation_id: int) -> None:
        try:
            await self._handoff.mark_awaiting_human(conversation_id)
        except Exception:
            logger.exception(
                "Could not mark conversation %s as awaiting human",
                conversation_id,
            )
