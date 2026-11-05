from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ProcessingContext:
    user_message_id: int
    user_message_public_id: str
    conversation_id: int
    conversation_public_id: str
    customer_id: int
    customer_name: str
    content: str
    client_message_id: str | None
    webhook_url: str | None


@dataclass(frozen=True, slots=True)
class HistoryMessage:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class AppendedMessage:
    message_id: int
    public_id: str


@dataclass(frozen=True, slots=True)
class DeliveryTarget:
    assistant_message_id: int
    assistant_public_id: str
    conversation_public_id: str
    reply_to_public_id: str | None
    client_message_id: str | None
    content: str
    webhook_url: str | None
    delivery_status: str
    attempts: int
    is_fallback: bool
    citations: list[dict[str, Any]] = field(default_factory=list)
