from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth.domain.identity import CustomerIdentity
from app.modules.auth.presentation.dependencies import get_current_identity
from app.modules.complaints.application.exceptions import (
    ComplaintNotFoundError,
)
from app.modules.complaints.domain.complaint import Complaint
from app.modules.complaints.domain.complaint_enums import (
    ComplaintCategory,
    ComplaintStatus,
)
from app.modules.complaints.presentation.dependencies import (
    get_get_complaint_use_case,
    get_list_complaints_use_case,
)

CUSTOMER = CustomerIdentity(
    customer_id=1,
    name="Lucas",
    email="lucas@example.com",
    phone="67998123456",
    city="Campo Grande",
)
COMPLAINT = Complaint(
    complaint_id=1,
    public_id=uuid4(),
    conversation_id=10,
    customer_id=1,
    message_id=1,
    order_id=2,
    category=ComplaintCategory.DELIVERY,
    description="Pedido atrasado",
    created_at=datetime(2026, 1, 1, tzinfo=UTC),
)


@pytest.fixture(autouse=True)
def overrides() -> Iterator[None]:
    app.dependency_overrides[get_current_identity] = lambda: CUSTOMER
    yield
    app.dependency_overrides.clear()


class FakeList:
    async def execute(self, **kwargs):
        return [COMPLAINT], 1


class FakeGet:
    async def execute(self, public_id, *, customer_id: int):
        if public_id != COMPLAINT.public_id:
            raise ComplaintNotFoundError()
        return COMPLAINT


def test_list_complaints(client: TestClient) -> None:
    app.dependency_overrides[get_list_complaints_use_case] = (
        lambda: FakeList()
    )
    response = client.get("/complaints?status=open")
    assert response.status_code == 200
    assert response.json()["items"][0]["category"] == "delivery"


def test_get_complaint_and_not_found(client: TestClient) -> None:
    app.dependency_overrides[get_get_complaint_use_case] = (
        lambda: FakeGet()
    )
    assert client.get(f"/complaints/{COMPLAINT.public_id}").status_code == 200
    missing = client.get(f"/complaints/{uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["code"] == "complaint_not_found"
