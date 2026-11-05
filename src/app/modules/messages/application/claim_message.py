from app.modules.messages.application.interfaces import MessageRepository
from app.modules.messages.domain.message import Message

STALE_PROCESSING_SECONDS = 900


class ClaimMessageUseCase:
    def __init__(self, repository: MessageRepository) -> None:
        self._repository = repository

    async def execute(self, message_id: int) -> Message | None:
        return await self._repository.claim_for_processing(
            message_id, stale_after_seconds=STALE_PROCESSING_SECONDS
        )
