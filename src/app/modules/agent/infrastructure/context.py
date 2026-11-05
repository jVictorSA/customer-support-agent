from datetime import datetime
from typing import Any

from app.modules.agent.domain.context import (
    AppendedMessage,
    DeliveryTarget,
    HistoryMessage,
    ProcessingContext,
)
from app.modules.conversations.application.interfaces import (
    ConversationRepository,
)
from app.modules.customers.application.interfaces import CustomerRepository
from app.modules.messages.application.interfaces import (
    MessageRepository,
    TaskQueue,
)
from app.modules.messages.domain.message_enums import MessageRole

STALE_PROCESSING_SECONDS = 900


class MessageAgentContextAdapter:
    def __init__(
        self,
        *,
        messages: MessageRepository,
        conversations: ConversationRepository,
        customers: CustomerRepository,
        queue: TaskQueue,
    ) -> None:
        self._messages = messages
        self._conversations = conversations
        self._customers = customers
        self._queue = queue

    async def claim(
        self, message_id: int
    ) -> ProcessingContext | None:
        message = await self._messages.claim_for_processing(
            message_id, stale_after_seconds=STALE_PROCESSING_SECONDS
        )
        if message is None:
            return None
        return await self._context_for(message)

    async def load_context(
        self, message_id: int
    ) -> ProcessingContext | None:
        message = await self._messages.get_by_id(message_id)
        if message is None:
            return None
        return await self._context_for(message)

    async def _context_for(self, message) -> ProcessingContext | None:
        conversation = await self._conversations.get_by_id(
            message.conversation_id
        )
        if conversation is None:
            return None
        customer = await self._customers.get_by_id(
            conversation.customer_id
        )
        if customer is None:
            return None
        return ProcessingContext(
            user_message_id=message.message_id or 0,
            user_message_public_id=str(message.public_id),
            conversation_id=conversation.conversation_id or 0,
            conversation_public_id=str(conversation.public_id),
            customer_id=customer.customer_id or 0,
            customer_name=customer.name,
            content=message.content,
            client_message_id=message.client_message_id,
            webhook_url=message.webhook_url,
        )

    async def history(
        self, conversation_id: int, *, limit: int
    ) -> list[HistoryMessage]:
        messages = await self._messages.get_history(
            conversation_id, limit=limit
        )
        return [
            HistoryMessage(role=message.role.value, content=message.content)
            for message in messages
        ]

    async def complete_turn(
        self,
        *,
        user_message_id: int,
        content: str,
        metadata: dict[str, Any],
        deliver_via_webhook: bool,
        is_fallback: bool = False,
    ) -> AppendedMessage:
        from uuid import uuid4

        from app.modules.messages.domain.message import Message
        from app.modules.messages.domain.message_enums import (
            DeliveryStatus,
            MessageRole as Role,
            MessageStatus,
        )

        assistant = await self._messages.append_assistant_and_complete(
            user_message_id=user_message_id,
            assistant=Message(
                message_id=None,
                public_id=uuid4(),
                conversation_id=0,
                role=Role.ASSISTANT,
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
        assert assistant.message_id is not None
        return AppendedMessage(
            message_id=assistant.message_id,
            public_id=str(assistant.public_id),
        )

    async def fail(self, message_id: int, *, error_code: str) -> None:
        await self._messages.mark_failed(
            message_id, error_code=error_code
        )

    async def release_for_retry(self, message_id: int) -> None:
        await self._messages.release_for_retry(message_id)

    async def enqueue_webhook(self, assistant_message_id: int) -> None:
        await self._queue.enqueue_webhook_delivery(assistant_message_id)


class MessageDeliveryAdapter:
    def __init__(
        self,
        *,
        messages: MessageRepository,
        conversations: ConversationRepository,
    ) -> None:
        self._messages = messages
        self._conversations = conversations

    async def get_target(
        self, assistant_message_id: int
    ) -> DeliveryTarget | None:
        assistant = await self._messages.get_by_id(assistant_message_id)
        if assistant is None or assistant.role is not MessageRole.ASSISTANT:
            return None
        if assistant.reply_to_message_id is None:
            return None
        user = await self._messages.get_by_id(
            assistant.reply_to_message_id
        )
        if user is None:
            return None
        conversation = await self._conversations.get_by_id(
            assistant.conversation_id
        )
        if conversation is None:
            return None
        return DeliveryTarget(
            assistant_message_id=assistant.message_id or assistant_message_id,
            assistant_public_id=str(assistant.public_id),
            conversation_public_id=str(conversation.public_id),
            reply_to_public_id=(
                str(user.public_id) if user.public_id else None
            ),
            client_message_id=user.client_message_id,
            content=assistant.content,
            webhook_url=user.webhook_url,
            delivery_status=assistant.delivery_status.value,
            attempts=assistant.delivery_attempts,
            is_fallback=bool(assistant.metadata.get("is_fallback")),
            citations=list(assistant.metadata.get("citations") or []),
        )

    async def update_delivery(
        self,
        assistant_message_id: int,
        *,
        status: str,
        attempts: int,
        error_code: str | None,
        delivered_at: datetime | None,
    ) -> None:
        await self._messages.update_delivery(
            assistant_message_id,
            status=status,
            attempts=attempts,
            error_code=error_code,
            delivered_at=delivered_at,
        )
