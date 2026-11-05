from typing import Protocol

from app.modules.auth.domain.identity import (
    CustomerIdentity,
    IssuedToken,
    TokenClaims,
    TokenType,
)


class CustomerDirectory(Protocol):
    async def find_by_credentials(
        self, *, email: str, phone: str
    ) -> CustomerIdentity | None: ...

    async def get_by_id(self, customer_id: int) -> CustomerIdentity | None: ...


class TokenService(Protocol):
    def issue_access_token(
        self, *, customer_id: int, email: str, name: str
    ) -> IssuedToken: ...

    def issue_refresh_token(
        self, *, customer_id: int, email: str, name: str
    ) -> IssuedToken: ...

    def decode(
        self, token: str, *, expected_type: TokenType
    ) -> TokenClaims: ...
