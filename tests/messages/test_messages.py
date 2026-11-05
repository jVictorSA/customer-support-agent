from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth.domain.identity import CustomerIdentity
from app.modules.auth.presentation.dependencies import get_current_identity
from app.modules.messages.application.exceptions import (
    ConversationBusyError,
    InvalidWebhookUrlError,
)
from app.modules.messages.application.list_messages import (
    ListMessagesUseCase,
)
from app.modules.messages.application.submit_message import (
    SubmitMessageUseCase,
)
from app.modules.messages.application.webhooks import validate_webhook_url
from app.modules.messages.domain.message import Message
from app.modules.messages.domain.message_enums import (
    MessageRole,
    MessageStatus,
)
from app.modules.messages.presentation.dependencies import (
    get_list_messages_use_case,
    get_submit_message_use_case,
)

CUSTOMER = CustomerIdentity(
    customer_id=1,
    name="Lucas",
    email="lucas@example.com",
    phone="67998123456",
    city="Campo Grande",
)
CONVERSATION_ID = uuid4()
USER_MESSAGE = Message(
    message_id=1,
    public_id=uuid4(),
    conversation_id=10,
    role=MessageRole.USER,
    content="Quais violões até R$1000?",
    status=MessageStatus.QUEUED,
    created_at=datetime(2026, 1, 1, tzinfo=UTC),
)


@pytest.fixture(autouse=True)
def overrides() -> Iterator[None]:
    app.dependency_overrides[get_current_identity] = lambda: CUSTOMER
    yield
    app.dependency_overrides.clear()


class FakeSubmit:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    async def execute(self, **kwargs) -> Message:
        if self.error is not None:
            raise self.error
        return USER_MESSAGE


class FakeList:
    async def execute(self, public_id, **kwargs):
        return [USER_MESSAGE], 1


def test_submit_message(client: TestClient) -> None:
    app.dependency_overrides[get_submit_message_use_case] = (
        lambda: FakeSubmit()
    )
    response = client.post(
        f"/conversations/{CONVERSATION_ID}/messages",
        json={"content": "Quais violões até R$1000?"},
    )
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert response.json()["conversation_id"] == str(CONVERSATION_ID)


def test_submit_message_conflict(client: TestClient) -> None:
    app.dependency_overrides[get_submit_message_use_case] = (
        lambda: FakeSubmit(ConversationBusyError())
    )
    response = client.post(
        f"/conversations/{CONVERSATION_ID}/messages",
        json={"content": "Oi"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "conversation_busy"


def test_list_messages(client: TestClient) -> None:
    app.dependency_overrides[get_list_messages_use_case] = (
        lambda: FakeList()
    )
    response = client.get(
        f"/conversations/{CONVERSATION_ID}/messages?after_message_id={uuid4()}"
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["role"] == "user"


def test_messages_require_auth(client: TestClient) -> None:
    app.dependency_overrides.clear()
    response = client.get(f"/conversations/{CONVERSATION_ID}/messages")
    assert response.status_code == 401


def test_webhook_url_validation() -> None:
    assert (
        validate_webhook_url(
            "https://example.com/hook", allow_private_hosts=False
        )
        == "https://example.com/hook"
    )
    assert (
        validate_webhook_url(
            "http://localhost:9000/hook", allow_private_hosts=True
        )
        == "http://localhost:9000/hook"
    )
    with pytest.raises(InvalidWebhookUrlError):
        validate_webhook_url(
            "http://127.0.0.1/hook", allow_private_hosts=False
        )
    with pytest.raises(InvalidWebhookUrlError):
        validate_webhook_url("ftp://example.com/hook", allow_private_hosts=True)
