from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth.application.exceptions import (
    ExpiredTokenError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from app.modules.auth.application.login import (
    LoginUseCase,
    RefreshTokenUseCase,
)
from app.modules.auth.domain.identity import (
    CustomerIdentity,
    TokenType,
)
from app.modules.auth.infrastructure.jwt_service import JwtTokenService
from app.modules.auth.presentation.dependencies import (
    get_current_identity,
    get_login_use_case,
    get_refresh_token_use_case,
)

CUSTOMER = CustomerIdentity(
    customer_id=1,
    name="Lucas Mendes",
    email="lucas@example.com",
    phone="(67) 99812-3456",
    city="Campo Grande",
)


class FakeDirectory:
    def __init__(self, customer: CustomerIdentity | None = CUSTOMER) -> None:
        self.customer = customer

    async def find_by_credentials(self, *, email: str, phone: str):
        if self.customer is None:
            return None
        if email != "lucas@example.com" or phone != "67998123456":
            return None
        return self.customer

    async def get_by_id(self, customer_id: int):
        if self.customer is not None and customer_id == 1:
            return self.customer
        return None


def _tokens() -> JwtTokenService:
    return JwtTokenService(
        secret="x" * 40,
        algorithm="HS256",
        access_expire_minutes=15,
        refresh_expire_days=7,
    )


@pytest.fixture(autouse=True)
def clear_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


async def test_login_and_refresh_flow() -> None:
    tokens = _tokens()
    login = LoginUseCase(directory=FakeDirectory(), tokens=tokens)
    result = await login.execute(
        email="LUCAS@example.com", phone="(67) 99812-3456"
    )

    claims = tokens.decode(
        result.access_token, expected_type=TokenType.ACCESS
    )
    assert claims.customer_id == 1
    assert result.refresh_expires_in == 7 * 86400

    refreshed = await RefreshTokenUseCase(
        tokens=tokens
    ).execute(refresh_token=result.refresh_token)
    assert tokens.decode(
        refreshed.access_token, expected_type=TokenType.ACCESS
    ).customer_id == 1


async def test_login_rejects_unknown_customer() -> None:
    login = LoginUseCase(
        directory=FakeDirectory(customer=None), tokens=_tokens()
    )
    with pytest.raises(InvalidCredentialsError):
        await login.execute(email="x@y.com", phone="67999999999")


def test_token_type_and_expiry_are_enforced() -> None:
    tokens = _tokens()
    refresh = tokens.issue_refresh_token(
        customer_id=1, email="a@b.com", name="A"
    )
    with pytest.raises(InvalidTokenError):
        tokens.decode(refresh.token, expected_type=TokenType.ACCESS)

    expired = JwtTokenService(
        secret="x" * 40,
        algorithm="HS256",
        access_expire_minutes=-1,
        refresh_expire_days=-1,
    )
    token = expired.issue_access_token(
        customer_id=1, email="a@b.com", name="A"
    )
    with pytest.raises(ExpiredTokenError):
        expired.decode(token.token, expected_type=TokenType.ACCESS)


def test_login_endpoint(client: TestClient) -> None:
    use_case = LoginUseCase(directory=FakeDirectory(), tokens=_tokens())
    app.dependency_overrides[get_login_use_case] = lambda: use_case

    response = client.post(
        "/auth/login",
        json={"email": "lucas@example.com", "phone": "(67) 99812-3456"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["customer"]["customer_id"] == 1
    assert payload["access_token"]


def test_login_endpoint_rejects_bad_credentials(client: TestClient) -> None:
    use_case = LoginUseCase(
        directory=FakeDirectory(customer=None), tokens=_tokens()
    )
    app.dependency_overrides[get_login_use_case] = lambda: use_case

    response = client.post(
        "/auth/login",
        json={"email": "x@y.com", "phone": "67999999999"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


def test_me_requires_token(client: TestClient) -> None:
    response = client.get("/auth/me")
    assert response.status_code == 401
    assert response.json()["code"] == "missing_token"


def test_me_returns_authenticated_customer(client: TestClient) -> None:
    app.dependency_overrides[get_current_identity] = lambda: CUSTOMER

    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "lucas@example.com"


def test_refresh_endpoint(client: TestClient) -> None:
    tokens = _tokens()
    refresh = tokens.issue_refresh_token(
        customer_id=1, email="lucas@example.com", name="Lucas"
    )
    app.dependency_overrides[get_refresh_token_use_case] = (
        lambda: RefreshTokenUseCase(tokens=tokens)
    )

    response = client.post(
        "/auth/refresh", json={"refresh_token": refresh.token}
    )

    assert response.status_code == 200
    assert response.json()["access_token"]
