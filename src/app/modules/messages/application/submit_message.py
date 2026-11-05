from uuid import uuid4

from app.modules.messages.application.conversation_access import (
    ConversationAccess,
)
from app.modules.messages.application.exceptions import (
    ConversationUnavailableError,
    MessageQueueUnavailableError,
)
from app.modules.messages.application.interfaces import (
    MessageRepository,
    TaskQueue,
)
from app.modules.messages.application.webhooks import validate_webhook_url
from app.modules.messages.domain.message import Message
from app.modules.messages.domain.message_enums import (
    MessageRole,
    MessageStatus,
)

STALE_PROCESSING_SECONDS = 900


class SubmitMessageUseCase:
    def __init__(
        self,
        *,
        conversations: ConversationAccess,
        messages: MessageRepository,
        queue: TaskQueue,
        allow_private_webhook_hosts: bool = False,
    ) -> None:
        self._conversations = conversations
        self._messages = messages
        self._queue = queue
        self._allow_private_webhook_hosts = allow_private_webhook_hosts

    async def execute(
        self,
        *,
        conversation_public_id,
        customer_id: int,
        content: str,
        webhook_url: str | None = None,
        client_message_id: str | None = None,
    ) -> Message:
        conversation = await self._conversations.get_by_public_id(
            conversation_public_id, customer_id=customer_id
        )
        if conversation is None:
            raise ConversationUnavailableError()

        if webhook_url is not None:
            webhook_url = validate_webhook_url(
                webhook_url,
                allow_private_hosts=self._allow_private_webhook_hosts,
            )

        message = await self._messages.create_user_message(
            Message(
                message_id=None,
                public_id=uuid4(),
                conversation_id=conversation.conversation_id,
                role=MessageRole.USER,
                content=content.strip(),
                status=MessageStatus.QUEUED,
                client_message_id=client_message_id,
                webhook_url=webhook_url,
            ),
            stale_after_seconds=STALE_PROCESSING_SECONDS,
        )

        if message.status is not MessageStatus.QUEUED:
            return message

        assert message.message_id is not None
        try:
            await self._queue.enqueue_processing(message.message_id)
        except Exception as exc:
            await self._messages.mark_failed(
                message.message_id, error_code="queue_unavailable"
            )
            raise MessageQueueUnavailableError() from exc
        return message
