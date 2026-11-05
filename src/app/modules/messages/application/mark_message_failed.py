from app.modules.messages.application.interfaces import MessageRepository


class MarkMessageFailedUseCase:
    def __init__(self, repository: MessageRepository) -> None:
        self._repository = repository

    async def execute(self, message_id: int, *, error_code: str) -> None:
        await self._repository.mark_failed(
            message_id, error_code=error_code
        )
