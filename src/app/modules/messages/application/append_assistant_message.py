from typing import Any
from uuid import uuid4

from app.modules.messages.application.interfaces import MessageRepository
from app.modules.messages.domain.message import Message
from app.modules.messages.domain.message_enums import (
    DeliveryStatus,
    MessageRole,
    MessageStatus,
)


class AppendAssistantMessageUseCase:
    def __init__(self, repository: MessageRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        user_message_id: int,
        content: str,
        metadata: dict[str, Any],
        deliver_via_webhook: bool,
        is_fallback: bool = False,
    ) -> Message:
        return await self._repository.append_assistant_and_complete(
            user_message_id=user_message_id,
            assistant=Message(
                message_id=None,
                public_id=uuid4(),
                conversation_id=0,
                role=MessageRole.ASSISTANT,
                content=content,
                status=MessageStatus.COMPLETED,
                reply_to_message_id=user_message_id,
                delivery_status=(
                    DeliveryStatus.PENDING
                    if deliver_via_webhook
                    else DeliveryStatus.NOT_REQUESTED
                ),
                metadata={**metadata, "is_fallback": is_fallback},
            ),
        )
