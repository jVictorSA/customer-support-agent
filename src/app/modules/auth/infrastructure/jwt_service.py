from datetime import UTC, datetime, timedelta

import jwt

from app.modules.auth.application.exceptions import (
    ExpiredTokenError,
    InvalidTokenError,
)
from app.modules.auth.domain.identity import (
    IssuedToken,
    TokenClaims,
    TokenType,
)


class JwtTokenService:
    """Stateless JWT issuer/verifier backed by PyJWT."""

    def __init__(
        self,
        *,
        secret: str,
        algorithm: str,
        access_expire_minutes: int,
        refresh_expire_days: int,
    ) -> None:
        self._secret = secret
        self._algorithm = algorithm
        self._access_expire = timedelta(minutes=access_expire_minutes)
        self._refresh_expire = timedelta(days=refresh_expire_days)

    def issue_access_token(
        self, *, customer_id: int, email: str, name: str
    ) -> IssuedToken:
        return self._issue(
            customer_id=customer_id,
            email=email,
            name=name,
            token_type=TokenType.ACCESS,
            lifetime=self._access_expire,
        )

    def issue_refresh_token(
        self, *, customer_id: int, email: str, name: str
    ) -> IssuedToken:
        return self._issue(
            customer_id=customer_id,
            email=email,
            name=name,
            token_type=TokenType.REFRESH,
            lifetime=self._refresh_expire,
        )

    def decode(self, token: str, *, expected_type: TokenType) -> TokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                options={"require": ["sub", "exp", "type"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise ExpiredTokenError() from exc
        except jwt.InvalidTokenError as exc:
            raise InvalidTokenError() from exc

        raw_type = payload.get("type")
        if raw_type != expected_type.value:
            raise InvalidTokenError()

        try:
            customer_id = int(payload["sub"])
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidTokenError() from exc

        return TokenClaims(
            customer_id=customer_id,
            email=str(payload.get("email", "")),
            name=str(payload.get("name", "")),
            token_type=expected_type,
        )

    def _issue(
        self,
        *,
        customer_id: int,
        email: str,
        name: str,
        token_type: TokenType,
        lifetime: timedelta,
    ) -> IssuedToken:
        now = datetime.now(UTC)
        payload = {
            "sub": str(customer_id),
            "email": email,
            "name": name,
            "type": token_type.value,
            "iat": now,
            "exp": now + lifetime,
        }
        token = jwt.encode(payload, self._secret, algorithm=self._algorithm)
        return IssuedToken(
            token=token, expires_in=int(lifetime.total_seconds())
        )
