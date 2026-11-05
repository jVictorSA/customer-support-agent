from app.modules.complaints.application.interfaces import (
    ConversationHandoff,
)
from app.modules.conversations.infrastructure.repository import (
    SqlAlchemyConversationRepository,
)


class RepositoryConversationHandoff:
    def __init__(self, repository: SqlAlchemyConversationRepository) -> None:
        self._repository = repository

    async def mark_awaiting_human(self, conversation_id: int) -> None:
        await self._repository.mark_awaiting_human(
            conversation_id, awaiting=True
        )
