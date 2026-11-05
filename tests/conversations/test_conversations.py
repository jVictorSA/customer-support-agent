from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth.domain.identity import CustomerIdentity
from app.modules.auth.presentation.dependencies import get_current_identity
from app.modules.conversations.application.exceptions import (
    ConversationNotFoundError,
)
from app.modules.conversations.application.create_conversation import (
    CreateConversationUseCase,
)
from app.modules.conversations.application.get_conversation import (
    GetConversationUseCase,
)
from app.modules.conversations.application.list_conversations import (
    ListConversationsUseCase,
)
from app.modules.conversations.domain.conversation import Conversation
from app.modules.conversations.presentation.dependencies import (
    get_create_conversation_use_case,
    get_get_conversation_use_case,
    get_list_conversations_use_case,
)

CUSTOMER = CustomerIdentity(
    customer_id=1,
    name="Lucas",
    email="lucas@example.com",
    phone="67998123456",
    city="Campo Grande",
)

CONVERSATION = Conversation(
    conversation_id=10,
    public_id=uuid4(),
    customer_id=1,
    created_at=datetime(2026, 1, 1, tzinfo=UTC),
    updated_at=datetime(2026, 1, 1, tzinfo=UTC),
)


@pytest.fixture(autouse=True)
def overrides() -> Iterator[None]:
    app.dependency_overrides[get_current_identity] = lambda: CUSTOMER
    yield
    app.dependency_overrides.clear()


class FakeCreate:
    async def execute(self, *, customer_id: int) -> Conversation:
        assert customer_id == 1
        return CONVERSATION


class FakeList:
    async def execute(self, **kwargs):
        return [CONVERSATION], 1


class FakeGet:
    async def execute(self, public_id, *, customer_id: int):
        if public_id != CONVERSATION.public_id:
            raise ConversationNotFoundError()
        return CONVERSATION


def test_create_conversation(client: TestClient) -> None:
    app.dependency_overrides[get_create_conversation_use_case] = (
        lambda: FakeCreate()
    )
    response = client.post("/conversations")
    assert response.status_code == 201
    assert response.json()["status"] == "active"
    assert response.json()["awaiting_human"] is False


def test_list_conversations(client: TestClient) -> None:
    app.dependency_overrides[get_list_conversations_use_case] = (
        lambda: FakeList()
    )
    response = client.get("/conversations?page=1&page_size=10")
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_get_conversation_and_not_found(client: TestClient) -> None:
    app.dependency_overrides[get_get_conversation_use_case] = (
        lambda: FakeGet()
    )
    found = client.get(f"/conversations/{CONVERSATION.public_id}")
    missing = client.get(f"/conversations/{uuid4()}")
    assert found.status_code == 200
    assert missing.status_code == 404
    assert missing.json()["code"] == "conversation_not_found"


def test_conversations_require_auth(client: TestClient) -> None:
    app.dependency_overrides.clear()
    response = client.get("/conversations")
    assert response.status_code == 401
