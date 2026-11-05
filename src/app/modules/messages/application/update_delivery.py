from datetime import datetime

from app.modules.messages.application.interfaces import MessageRepository


class UpdateDeliveryUseCase:
    def __init__(self, repository: MessageRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        message_id: int,
        *,
        status: str,
        attempts: int,
        error_code: str | None,
        delivered_at: datetime | None,
    ) -> None:
        await self._repository.update_delivery(
            message_id,
            status=status,
            attempts=attempts,
            error_code=error_code,
            delivered_at=delivered_at,
        )
