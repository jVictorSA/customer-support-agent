import asyncio
import logging
from dataclasses import dataclass

from customer_support_agent.modules.health.application.ports import HealthRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DatabaseHealthResult:
    is_up: bool
    detail: str | None = None


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
