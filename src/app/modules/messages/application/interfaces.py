from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.modules.messages.domain.message import Message


class MessageRepository(Protocol):
    async def create_user_message(
        self, message: Message, *, stale_after_seconds: int
    ) -> Message: ...

    async def get_by_public_id(
        self, public_id: UUID, *, conversation_id: int
    ) -> Message | None: ...

    async def get_by_id(self, message_id: int) -> Message | None: ...

    async def list_by_conversation(
        self,
        conversation_id: int,
        *,
        offset: int,
        limit: int,
        after_message_id: int | None = None,
    ) -> tuple[list[Message], int]: ...

    async def get_history(
        self, conversation_id: int, *, limit: int
    ) -> list[Message]: ...

    async def claim_for_processing(
        self, message_id: int, *, stale_after_seconds: int
    ) -> Message | None: ...

    async def append_assistant_and_complete(
        self, *, user_message_id: int, assistant: Message
    ) -> Message: ...

    async def mark_failed(
        self, message_id: int, *, error_code: str
    ) -> None: ...

    async def release_for_retry(self, message_id: int) -> None: ...

    async def update_delivery(
        self,
        message_id: int,
        *,
        status: str,
        attempts: int,
        error_code: str | None,
        delivered_at: datetime | None,
    ) -> None: ...


class TaskQueue(Protocol):
    async def enqueue_processing(self, message_id: int) -> None: ...

    async def enqueue_webhook_delivery(
        self, assistant_message_id: int
    ) -> None: ...
