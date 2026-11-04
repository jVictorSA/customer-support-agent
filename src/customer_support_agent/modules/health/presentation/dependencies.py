from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from customer_support_agent.core.config import get_settings
from customer_support_agent.db.session import get_session
from customer_support_agent.modules.health.application.check_database_health import (
    CheckDatabaseHealthUseCase,
)
from customer_support_agent.modules.health.application.ports import HealthRepository
from customer_support_agent.modules.health.infrastructure.persistence.repository import (
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
