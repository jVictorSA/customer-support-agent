import re
from dataclasses import dataclass
from enum import StrEnum


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


@dataclass(frozen=True, slots=True)
class CustomerIdentity:
    """The authenticated customer attached to a request."""

    customer_id: int
    name: str
    email: str
    phone: str
    city: str


@dataclass(frozen=True, slots=True)
class TokenClaims:
    customer_id: int
    email: str
    name: str
    token_type: TokenType


@dataclass(frozen=True, slots=True)
class IssuedToken:
    token: str
    expires_in: int


def normalize_email(value: str) -> str:
    return value.strip().lower()


def normalize_phone(value: str) -> str:
    """Keep only digits so formatted and unformatted phones compare equal."""
    return re.sub(r"\D", "", value)
