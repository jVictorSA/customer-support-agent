from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session
from app.modules.health.application.check_database_health import (
    CheckDatabaseHealthUseCase,
)
from app.modules.health.application.interfaces import HealthRepository
from app.modules.health.infrastructure.repository import (
    SqlAlchemyHealthRepository,
)


def get_health_repository(
    session: AsyncSession = Depends(get_session),
) -> HealthRepository:
    return SqlAlchemyHealthRepository(session)


def get_check_database_health_use_case(
    repository: HealthRepository = Depends(get_health_repository),
) -> CheckDatabaseHealthUseCase:
    return CheckDatabaseHealthUseCase(
        repository=repository,
        timeout=get_settings().db_healthcheck_timeout,
    )
