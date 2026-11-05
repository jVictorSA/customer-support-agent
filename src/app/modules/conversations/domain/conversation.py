from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.conversations.domain.conversation_status import (
    ConversationStatus,
)


@dataclass(frozen=True, slots=True)
class Conversation:
    conversation_id: int | None
    public_id: UUID
    customer_id: int
    status: ConversationStatus = ConversationStatus.ACTIVE
    awaiting_human: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
