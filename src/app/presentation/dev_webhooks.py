import hashlib
import hmac
import logging

from fastapi import APIRouter, Request, Response

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dev/webhooks", tags=["Dev"])


class InvalidWebhookSignatureError(AuthenticationError):
    code = "invalid_webhook_signature"
    message = "Webhook signature is invalid"


@router.post("/conversation", status_code=204)
async def receive_conversation_webhook(request: Request) -> Response:
    settings = get_settings()
    body = await request.body()
    timestamp = request.headers.get("X-Webhook-Timestamp", "")
    signature = request.headers.get("X-Webhook-Signature", "")
    expected = hmac.new(
        settings.conversation_webhook_secret.get_secret_value().encode(),
        f"{timestamp}.".encode() + body,
        hashlib.sha256,
    ).hexdigest()
    if not signature or not hmac.compare_digest(
        signature, f"sha256={expected}"
    ):
        raise InvalidWebhookSignatureError()

    logger.info(
        "Development webhook received id=%s bytes=%s",
        request.headers.get("X-Webhook-Id"),
        len(body),
    )
    return Response(status_code=204)
