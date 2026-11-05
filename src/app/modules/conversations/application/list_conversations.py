from app.modules.conversations.application.interfaces import (
    ConversationRepository,
)
from app.modules.conversations.domain.conversation import Conversation


class ListConversationsUseCase:
    def __init__(self, repository: ConversationRepository) -> None:
        self._repository = repository

    async def execute(
        self, *, customer_id: int, page: int, page_size: int
    ) -> tuple[list[Conversation], int]:
        return await self._repository.list_by_customer(
            customer_id=customer_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
