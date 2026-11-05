from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.modules.conversations.application.create_conversation import (
    CreateConversationUseCase,
)
from app.modules.conversations.application.get_conversation import (
    GetConversationUseCase,
)
from app.modules.conversations.application.interfaces import (
    ConversationRepository,
)
from app.modules.conversations.application.list_conversations import (
    ListConversationsUseCase,
)
from app.modules.conversations.infrastructure.repository import (
    SqlAlchemyConversationRepository,
)


def get_conversation_repository(
    session: AsyncSession = Depends(get_session),
) -> ConversationRepository:
    return SqlAlchemyConversationRepository(session)


def get_create_conversation_use_case(
    repository: ConversationRepository = Depends(
        get_conversation_repository
    ),
) -> CreateConversationUseCase:
    return CreateConversationUseCase(repository)


def get_list_conversations_use_case(
    repository: ConversationRepository = Depends(
        get_conversation_repository
    ),
) -> ListConversationsUseCase:
    return ListConversationsUseCase(repository)


def get_get_conversation_use_case(
    repository: ConversationRepository = Depends(
        get_conversation_repository
    ),
) -> GetConversationUseCase:
    return GetConversationUseCase(repository)
