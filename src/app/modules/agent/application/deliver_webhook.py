import logging
import time
from datetime import UTC, datetime

from app.modules.agent.application.interfaces import (
    DeliveryTargetPort,
    WebhookSender,
)

logger = logging.getLogger(__name__)


class DeliverWebhookUseCase:
    def __init__(
        self,
        *,
        targets: DeliveryTargetPort,
        sender: WebhookSender,
    ) -> None:
        self._targets = targets
        self._sender = sender

    async def execute(self, assistant_message_id: int) -> None:
        target = await self._targets.get_target(assistant_message_id)
        if target is None:
            return
        if target.webhook_url is None:
            return
        if target.delivery_status == "delivered":
            return

        attempts = target.attempts + 1
        await self._targets.update_delivery(
            assistant_message_id,
            status="pending",
            attempts=attempts,
            error_code=None,
            delivered_at=None,
        )
        payload = {
            "version": "1",
            "event": "conversation.message.completed",
            "conversation_id": target.conversation_public_id,
            "client_message_id": target.client_message_id,
            "message": {
                "id": target.assistant_public_id,
                "reply_to_message_id": target.reply_to_public_id,
                "role": "assistant",
                "content": target.content,
                "is_fallback": target.is_fallback,
                "citations": target.citations,
                "created_at": datetime.now(UTC).isoformat(),
            },
        }
        timestamp = int(time.time())
        try:
            await self._sender.send(
                url=target.webhook_url,
                payload=payload,
                timestamp=timestamp,
            )
        except Exception as exc:
            logger.warning(
                "Webhook delivery failed for message %s (attempt %s)",
                assistant_message_id,
                attempts,
            )
            await self._targets.update_delivery(
                assistant_message_id,
                status="failed",
                attempts=attempts,
                error_code="webhook_delivery_failed",
                delivered_at=None,
            )
            raise

        await self._targets.update_delivery(
            assistant_message_id,
            status="delivered",
            attempts=attempts,
            error_code=None,
            delivered_at=datetime.now(UTC),
        )
