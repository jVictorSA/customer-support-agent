from uuid import uuid4

from app.modules.conversations.application.interfaces import (
    ConversationRepository,
)
from app.modules.conversations.domain.conversation import Conversation


class CreateConversationUseCase:
    def __init__(self, repository: ConversationRepository) -> None:
        self._repository = repository

    async def execute(self, *, customer_id: int) -> Conversation:
        return await self._repository.create(
            Conversation(
                conversation_id=None,
                public_id=uuid4(),
                customer_id=customer_id,
            )
        )
