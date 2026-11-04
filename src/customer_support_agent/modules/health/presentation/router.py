from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from customer_support_agent.core.config import Settings, get_settings
from customer_support_agent.modules.health.application.check_database_health import (
    CheckDatabaseHealthUseCase,
)
from customer_support_agent.modules.health.presentation.dependencies import (
    get_check_database_health_use_case,
)
from customer_support_agent.modules.health.presentation.schemas import (
    DatabaseHealthResponse,
    HealthResponse,
)

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse()


@router.get(
    "/db",
    response_model=DatabaseHealthResponse,
    response_model_exclude_none=True,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": DatabaseHealthResponse,
            "description": "Database is unavailable",
        }
    },
)
async def database_health_check(
    use_case: CheckDatabaseHealthUseCase = Depends(
        get_check_database_health_use_case
    ),
    settings: Settings = Depends(get_settings),
) -> DatabaseHealthResponse | JSONResponse:
    result = await use_case.execute()
    detail = result.detail if settings.is_development else None

    payload = DatabaseHealthResponse(
        status="ok" if result.is_up else "degraded",
        database="up" if result.is_up else "down",
        detail=detail,
    )

    if not result.is_up:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=payload.model_dump(exclude_none=True),
        )

    return payload
