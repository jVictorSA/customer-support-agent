from typing import Protocol
from uuid import UUID

from app.modules.conversations.domain.conversation import Conversation


class ConversationRepository(Protocol):
    async def create(self, conversation: Conversation) -> Conversation: ...

    async def get_by_public_id(
        self, public_id: UUID, *, customer_id: int
    ) -> Conversation | None: ...

    async def get_by_id(
        self, conversation_id: int
    ) -> Conversation | None: ...

    async def list_by_customer(
        self, *, customer_id: int, offset: int, limit: int
    ) -> tuple[list[Conversation], int]: ...

    async def mark_awaiting_human(
        self, conversation_id: int, *, awaiting: bool = True
    ) -> None: ...
