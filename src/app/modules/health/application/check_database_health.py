import asyncio
import logging

from app.modules.health.application.interfaces import HealthRepository
from app.modules.health.domain.health import DatabaseHealthResult

logger = logging.getLogger(__name__)


class CheckDatabaseHealthUseCase:
    def __init__(self, repository: HealthRepository, timeout: float) -> None:
        self._repository = repository
        self._timeout = timeout

    async def execute(self) -> DatabaseHealthResult:
        try:
            await asyncio.wait_for(self._repository.ping(), timeout=self._timeout)
        except Exception as exc:
            logger.warning("Database health check failed", exc_info=True)
            message = str(exc)
            detail = (
                f"{type(exc).__name__}: {message}"
                if message
                else type(exc).__name__
            )
            return DatabaseHealthResult(is_up=False, detail=detail)

        return DatabaseHealthResult(is_up=True)
