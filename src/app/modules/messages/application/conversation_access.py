from typing import Protocol
from uuid import UUID

from app.modules.messages.domain.conversation_ref import ConversationRef


class ConversationAccess(Protocol):
    async def get_by_public_id(
        self, public_id: UUID, *, customer_id: int
    ) -> ConversationRef | None: ...
