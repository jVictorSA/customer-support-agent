from app.modules.conversations.application.interfaces import (
    ConversationRepository,
)


class MarkAwaitingHumanUseCase:
    def __init__(self, repository: ConversationRepository) -> None:
        self._repository = repository

    async def execute(
        self, conversation_id: int, *, awaiting: bool = True
    ) -> None:
        await self._repository.mark_awaiting_human(
            conversation_id, awaiting=awaiting
        )
