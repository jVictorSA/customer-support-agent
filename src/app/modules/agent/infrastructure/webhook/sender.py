import hashlib
import hmac
import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class WebhookDeliveryError(Exception):
    pass


class HttpWebhookSender:
    def __init__(
        self,
        *,
        secret: str,
        timeout: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._secret = secret
        self._timeout = timeout
        self._transport = transport

    async def send(
        self,
        *,
        url: str,
        payload: dict[str, Any],
        timestamp: int,
    ) -> None:
        body = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        signature = hmac.new(
            self._secret.encode("utf-8"),
            f"{timestamp}.".encode("utf-8") + body,
            hashlib.sha256,
        ).hexdigest()

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                transport=self._transport,
                follow_redirects=False,
            ) as client:
                response = await client.post(
                    url,
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Webhook-Id": str(payload.get("message", {}).get("id", "")),
                        "X-Webhook-Timestamp": str(timestamp),
                        "X-Webhook-Signature": f"sha256={signature}",
                    },
                )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise WebhookDeliveryError("webhook transport failure") from exc

        if response.status_code >= 300:
            raise WebhookDeliveryError(
                f"webhook returned {response.status_code}"
            )
