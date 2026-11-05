from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session
from app.modules.auth.application.exceptions import MissingTokenError
from app.modules.auth.application.interfaces import (
    CustomerDirectory,
    TokenService,
)
from app.modules.auth.application.login import (
    AuthenticateTokenUseCase,
    LoginUseCase,
    RefreshTokenUseCase,
)
from app.modules.auth.domain.identity import CustomerIdentity
from app.modules.auth.infrastructure.customer_directory import (
    RepositoryCustomerDirectory,
)
from app.modules.auth.infrastructure.jwt_service import JwtTokenService
from app.modules.customers.infrastructure.repository import (
    SqlAlchemyCustomerRepository,
)

_bearer = HTTPBearer(auto_error=False)


def get_token_service() -> TokenService:
    settings = get_settings()
    return JwtTokenService(
        secret=settings.auth_jwt_secret.get_secret_value(),
        algorithm=settings.auth_jwt_algorithm,
        access_expire_minutes=settings.auth_access_token_expire_minutes,
        refresh_expire_days=settings.auth_refresh_token_expire_days,
    )


def get_customer_directory(
    session: AsyncSession = Depends(get_session),
) -> CustomerDirectory:
    return RepositoryCustomerDirectory(
        SqlAlchemyCustomerRepository(session)
    )


def get_login_use_case(
    directory: CustomerDirectory = Depends(get_customer_directory),
    tokens: TokenService = Depends(get_token_service),
) -> LoginUseCase:
    return LoginUseCase(directory=directory, tokens=tokens)


def get_refresh_token_use_case(
    tokens: TokenService = Depends(get_token_service),
) -> RefreshTokenUseCase:
    return RefreshTokenUseCase(tokens=tokens)


def get_authenticate_token_use_case(
    directory: CustomerDirectory = Depends(get_customer_directory),
    tokens: TokenService = Depends(get_token_service),
) -> AuthenticateTokenUseCase:
    return AuthenticateTokenUseCase(directory=directory, tokens=tokens)


async def get_current_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    use_case: AuthenticateTokenUseCase = Depends(
        get_authenticate_token_use_case
    ),
) -> CustomerIdentity:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise MissingTokenError()
    return await use_case.execute(credentials.credentials)
