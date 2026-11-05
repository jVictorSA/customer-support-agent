from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.messages.domain.message import Message
from app.modules.messages.domain.message_enums import (
    DeliveryStatus,
    MessageRole,
    MessageStatus,
)


class SubmitMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    webhook_url: str | None = Field(default=None, max_length=2048)
    client_message_id: str | None = Field(
        default=None, min_length=1, max_length=128
    )


class MessageResponse(BaseModel):
    public_id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    status: MessageStatus
    client_message_id: str | None
    reply_to_message_id: UUID | None
    delivery_status: DeliveryStatus
    delivery_attempts: int
    error_code: str | None
    is_fallback: bool
    created_at: datetime

    @classmethod
    def from_domain(
        cls, message: Message, *, conversation_public_id: UUID
    ) -> "MessageResponse":
        assert message.created_at is not None
        return cls(
            public_id=message.public_id,
            conversation_id=conversation_public_id,
            role=message.role,
            content=message.content,
            status=message.status,
            client_message_id=message.client_message_id,
            reply_to_message_id=message.reply_to_public_id,
            delivery_status=message.delivery_status,
            delivery_attempts=message.delivery_attempts,
            error_code=message.error_code,
            is_fallback=bool(message.metadata.get("is_fallback")),
            created_at=message.created_at,
        )
