from uuid import UUID

from app.modules.conversations.application.exceptions import (
    ConversationNotFoundError,
)
from app.modules.conversations.application.interfaces import (
    ConversationRepository,
)
from app.modules.conversations.domain.conversation import Conversation


class GetConversationUseCase:
    def __init__(self, repository: ConversationRepository) -> None:
        self._repository = repository

    async def execute(
        self, public_id: UUID, *, customer_id: int
    ) -> Conversation:
        conversation = await self._repository.get_by_public_id(
            public_id, customer_id=customer_id
        )
        if conversation is None:
            raise ConversationNotFoundError()
        return conversation
