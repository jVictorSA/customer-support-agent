from enum import StrEnum


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class MessageStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DeliveryStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
