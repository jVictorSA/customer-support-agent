from uuid import UUID

from app.modules.messages.application.conversation_access import (
    ConversationAccess,
)
from app.modules.messages.application.exceptions import (
    ConversationUnavailableError,
    MessageNotFoundError,
)
from app.modules.messages.application.interfaces import MessageRepository
from app.modules.messages.domain.message import Message


class ListMessagesUseCase:
    def __init__(
        self,
        *,
        conversations: ConversationAccess,
        messages: MessageRepository,
    ) -> None:
        self._conversations = conversations
        self._messages = messages

    async def execute(
        self,
        conversation_public_id: UUID,
        *,
        customer_id: int,
        page: int,
        page_size: int,
        after_message_id: UUID | None = None,
    ) -> tuple[list[Message], int]:
        conversation = await self._conversations.get_by_public_id(
            conversation_public_id, customer_id=customer_id
        )
        if conversation is None:
            raise ConversationUnavailableError()

        after_internal_id: int | None = None
        if after_message_id is not None:
            after = await self._messages.get_by_public_id(
                after_message_id,
                conversation_id=conversation.conversation_id,
            )
            if after is None:
                raise MessageNotFoundError()
            after_internal_id = after.message_id

        return await self._messages.list_by_conversation(
            conversation.conversation_id,
            offset=(page - 1) * page_size,
            limit=page_size,
            after_message_id=after_internal_id,
        )
