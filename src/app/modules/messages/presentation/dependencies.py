from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session
from app.modules.conversations.infrastructure.repository import (
    SqlAlchemyConversationRepository,
)
from app.modules.messages.application.conversation_access import (
    ConversationAccess,
)
from app.modules.messages.application.interfaces import (
    MessageRepository,
    TaskQueue,
)
from app.modules.messages.application.list_messages import (
    ListMessagesUseCase,
)
from app.modules.messages.application.submit_message import (
    SubmitMessageUseCase,
)
from app.modules.messages.infrastructure.conversation_access import (
    RepositoryConversationAccess,
)
from app.modules.messages.infrastructure.queue.celery_queue import (
    CeleryConversationQueue,
)
from app.modules.messages.infrastructure.repository import (
    SqlAlchemyMessageRepository,
)


def get_message_repository(
    session: AsyncSession = Depends(get_session),
) -> MessageRepository:
    return SqlAlchemyMessageRepository(session)


def get_conversation_access(
    session: AsyncSession = Depends(get_session),
) -> ConversationAccess:
    return RepositoryConversationAccess(
        SqlAlchemyConversationRepository(session)
    )


def get_task_queue() -> TaskQueue:
    return CeleryConversationQueue()


def get_submit_message_use_case(
    conversations: ConversationAccess = Depends(get_conversation_access),
    messages: MessageRepository = Depends(get_message_repository),
    queue: TaskQueue = Depends(get_task_queue),
) -> SubmitMessageUseCase:
    return SubmitMessageUseCase(
        conversations=conversations,
        messages=messages,
        queue=queue,
        allow_private_webhook_hosts=(
            get_settings().conversation_webhook_allow_private_hosts
        ),
    )


def get_list_messages_use_case(
    conversations: ConversationAccess = Depends(get_conversation_access),
    messages: MessageRepository = Depends(get_message_repository),
) -> ListMessagesUseCase:
    return ListMessagesUseCase(
        conversations=conversations, messages=messages
    )
