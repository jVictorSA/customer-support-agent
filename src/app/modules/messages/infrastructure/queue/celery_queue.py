import asyncio

from celery import Celery

from app.core.config import get_settings


class CeleryConversationQueue:
    """Thin Celery client used by the API process to enqueue work."""

    def __init__(self) -> None:
        self._app = Celery(
            "customer_support_agent",
            broker=get_settings().rabbitmq_url,
        )

    async def enqueue_processing(self, message_id: int) -> None:
        await asyncio.to_thread(
            self._app.send_task,
            "conversations.process",
            args=[message_id],
            queue="conversations.process",
        )

    async def enqueue_webhook_delivery(
        self, assistant_message_id: int
    ) -> None:
        await asyncio.to_thread(
            self._app.send_task,
            "conversations.deliver_webhook",
            args=[assistant_message_id],
            queue="conversations.process",
        )
