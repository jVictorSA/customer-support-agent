from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ConversationRef:
    conversation_id: int
    public_id: UUID
