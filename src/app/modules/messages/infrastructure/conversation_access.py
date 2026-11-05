from uuid import UUID

from app.modules.conversations.infrastructure.repository import (
    SqlAlchemyConversationRepository,
)
from app.modules.messages.domain.conversation_ref import ConversationRef


class RepositoryConversationAccess:
    def __init__(self, repository: SqlAlchemyConversationRepository) -> None:
        self._repository = repository

    async def get_by_public_id(
        self, public_id: UUID, *, customer_id: int
    ) -> ConversationRef | None:
        conversation = await self._repository.get_by_public_id(
            public_id, customer_id=customer_id
        )
        if conversation is None or conversation.conversation_id is None:
            return None
        return ConversationRef(
            conversation_id=conversation.conversation_id,
            public_id=conversation.public_id,
        )
