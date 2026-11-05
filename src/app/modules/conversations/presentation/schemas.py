from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.modules.conversations.domain.conversation import Conversation
from app.modules.conversations.domain.conversation_status import (
    ConversationStatus,
)


class ConversationResponse(BaseModel):
    public_id: UUID
    status: ConversationStatus
    awaiting_human: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, conversation: Conversation) -> "ConversationResponse":
        assert conversation.created_at is not None
        assert conversation.updated_at is not None
        return cls(
            public_id=conversation.public_id,
            status=conversation.status,
            awaiting_human=conversation.awaiting_human,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )
