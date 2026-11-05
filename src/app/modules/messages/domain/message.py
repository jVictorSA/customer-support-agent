from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from app.modules.messages.domain.message_enums import (
    DeliveryStatus,
    MessageRole,
    MessageStatus,
)


@dataclass(frozen=True, slots=True)
class Message:
    message_id: int | None
    public_id: UUID
    conversation_id: int
    role: MessageRole
    content: str
    status: MessageStatus
    client_message_id: str | None = None
    reply_to_message_id: int | None = None
    reply_to_public_id: UUID | None = None
    webhook_url: str | None = None
    delivery_status: DeliveryStatus = DeliveryStatus.NOT_REQUESTED
    delivery_attempts: int = 0
    delivered_at: datetime | None = None
    last_delivery_error_code: str | None = None
    error_code: str | None = None
    processing_started_at: datetime | None = None
    processed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
