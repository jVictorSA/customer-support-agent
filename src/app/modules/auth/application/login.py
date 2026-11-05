from app.modules.auth.application.exceptions import InvalidCredentialsError
from app.modules.auth.application.interfaces import (
    CustomerDirectory,
    TokenService,
)
from app.modules.auth.domain.identity import (
    CustomerIdentity,
    TokenType,
    normalize_email,
    normalize_phone,
)
from app.modules.auth.domain.results import LoginResult, RefreshedToken


class LoginUseCase:
    def __init__(
        self,
        *,
        directory: CustomerDirectory,
        tokens: TokenService,
    ) -> None:
        self._directory = directory
        self._tokens = tokens

    async def execute(self, *, email: str, phone: str) -> LoginResult:
        customer = await self._directory.find_by_credentials(
            email=normalize_email(email),
            phone=normalize_phone(phone),
        )
        if customer is None:
            raise InvalidCredentialsError()

        access = self._tokens.issue_access_token(
            customer_id=customer.customer_id,
            email=customer.email,
            name=customer.name,
        )
        refresh = self._tokens.issue_refresh_token(
            customer_id=customer.customer_id,
            email=customer.email,
            name=customer.name,
        )
        return LoginResult(
            customer=customer,
            access_token=access.token,
            refresh_token=refresh.token,
            access_expires_in=access.expires_in,
            refresh_expires_in=refresh.expires_in,
        )


class RefreshTokenUseCase:
    def __init__(self, *, tokens: TokenService) -> None:
        self._tokens = tokens

    async def execute(self, *, refresh_token: str) -> RefreshedToken:
        claims = self._tokens.decode(
            refresh_token, expected_type=TokenType.REFRESH
        )
        access = self._tokens.issue_access_token(
            customer_id=claims.customer_id,
            email=claims.email,
            name=claims.name,
        )
        return RefreshedToken(
            access_token=access.token, expires_in=access.expires_in
        )


class AuthenticateTokenUseCase:
    def __init__(
        self,
        *,
        directory: CustomerDirectory,
        tokens: TokenService,
    ) -> None:
        self._directory = directory
        self._tokens = tokens

    async def execute(self, token: str) -> CustomerIdentity:
        claims = self._tokens.decode(token, expected_type=TokenType.ACCESS)
        customer = await self._directory.get_by_id(claims.customer_id)
        if customer is None:
            raise InvalidCredentialsError()
        return customer
