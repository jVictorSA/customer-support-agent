from fastapi import APIRouter, Depends

from app.modules.auth.application.login import (
    LoginUseCase,
    RefreshTokenUseCase,
)
from app.modules.auth.domain.identity import CustomerIdentity
from app.modules.auth.presentation.dependencies import (
    get_current_identity,
    get_login_use_case,
    get_refresh_token_use_case,
)
from app.modules.auth.presentation.schemas import (
    CustomerIdentityResponse,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    use_case: LoginUseCase = Depends(get_login_use_case),
) -> LoginResponse:
    result = await use_case.execute(
        email=payload.email, phone=payload.phone
    )
    return LoginResponse.from_result(result)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    payload: RefreshRequest,
    use_case: RefreshTokenUseCase = Depends(get_refresh_token_use_case),
) -> RefreshResponse:
    result = await use_case.execute(refresh_token=payload.refresh_token)
    return RefreshResponse(
        access_token=result.access_token, expires_in=result.expires_in
    )


@router.get("/me", response_model=CustomerIdentityResponse)
async def read_me(
    customer: CustomerIdentity = Depends(get_current_identity),
) -> CustomerIdentityResponse:
    return CustomerIdentityResponse.from_domain(customer)
