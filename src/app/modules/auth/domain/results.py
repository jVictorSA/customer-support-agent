from dataclasses import dataclass

from app.modules.auth.domain.identity import CustomerIdentity


@dataclass(frozen=True, slots=True)
class LoginResult:
    customer: CustomerIdentity
    access_token: str
    refresh_token: str
    access_expires_in: int
    refresh_expires_in: int


@dataclass(frozen=True, slots=True)
class RefreshedToken:
    access_token: str
    expires_in: int
