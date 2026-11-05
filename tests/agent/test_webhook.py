import hashlib
import hmac
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.modules.agent.application.deliver_webhook import (
    DeliverWebhookUseCase,
)
from app.modules.agent.domain.context import DeliveryTarget
from app.modules.agent.infrastructure.webhook.sender import (
    HttpWebhookSender,
    WebhookDeliveryError,
)

PAYLOAD = {
    "version": "1",
    "event": "conversation.message.completed",
    "conversation_id": "conversation",
    "message": {"id": "message", "content": "Oi"},
}


async def test_webhook_sender_signs_payload() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        captured["signature"] = request.headers["X-Webhook-Signature"]
        captured["id"] = request.headers["X-Webhook-Id"]
        return httpx.Response(204)

    sender = HttpWebhookSender(
        secret="secret",
        timeout=1,
        transport=httpx.MockTransport(handler),
    )
    await sender.send(
        url="https://example.com/hook", payload=PAYLOAD, timestamp=123
    )

    body = captured["body"]
    expected = hmac.new(
        b"secret", b"123." + body, hashlib.sha256
    ).hexdigest()
    assert captured["signature"] == f"sha256={expected}"
    assert captured["id"] == "message"


async def test_webhook_sender_raises_on_failure() -> None:
    sender = HttpWebhookSender(
        secret="secret",
        timeout=1,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(500)
        ),
    )
    with pytest.raises(WebhookDeliveryError):
        await sender.send(
            url="https://example.com/hook", payload=PAYLOAD, timestamp=1
        )


class FakeTargets:
    def __init__(self) -> None:
        self.updated = []

    async def get_target(self, assistant_message_id: int):
        return DeliveryTarget(
            assistant_message_id=assistant_message_id,
            assistant_public_id="assistant",
            conversation_public_id="conversation",
            reply_to_public_id="user",
            client_message_id="client",
            content="Oi",
            webhook_url="https://example.com/hook",
            delivery_status="pending",
            attempts=0,
            is_fallback=False,
        )

    async def update_delivery(self, message_id: int, **kwargs) -> None:
        self.updated.append((message_id, kwargs))


class FakeSender:
    async def send(self, **kwargs) -> None:
        pass


async def test_delivery_use_case_marks_delivered() -> None:
    targets = FakeTargets()
    use_case = DeliverWebhookUseCase(
        targets=targets, sender=FakeSender()
    )

    await use_case.execute(99)

    assert targets.updated[-1][0] == 99
    assert targets.updated[-1][1]["status"] == "delivered"
    assert targets.updated[-1][1]["attempts"] == 1


def test_dev_webhook_receiver_validates_signature(
    client: TestClient,
) -> None:
    body = json.dumps(PAYLOAD).encode()
    timestamp = str(int(time.time()))
    secret = (
        get_settings().conversation_webhook_secret.get_secret_value().encode()
    )
    signature = hmac.new(
        secret, f"{timestamp}.".encode() + body, hashlib.sha256
    ).hexdigest()

    valid = client.post(
        "/dev/webhooks/conversation",
        content=body,
        headers={
            "X-Webhook-Timestamp": timestamp,
            "X-Webhook-Signature": f"sha256={signature}",
            "Content-Type": "application/json",
        },
    )
    invalid = client.post(
        "/dev/webhooks/conversation",
        content=body,
        headers={
            "X-Webhook-Timestamp": timestamp,
            "X-Webhook-Signature": "sha256=invalid",
        },
    )

    assert valid.status_code == 204
    assert invalid.status_code == 401
    assert invalid.json()["code"] == "invalid_webhook_signature"
