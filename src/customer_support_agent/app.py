import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from customer_support_agent.core.config import get_settings
from customer_support_agent.db.session import get_engine, wait_for_database
from customer_support_agent.modules.health.presentation.router import (
    router as health_router,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()

    if settings.db_startup_check_enabled:
        connected = await wait_for_database(
            max_retries=settings.db_startup_max_retries,
            retry_delay=settings.db_startup_retry_delay,
        )
        if not connected:
            logger.warning(
                "Starting API in degraded mode: database is unavailable"
            )

    yield

    await get_engine().dispose()


app = FastAPI(
    title="Customer Support Agent API",
    description=(
        "API de agente de atendimento ao cliente para uma loja de instrumentos "
        "musicais."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)


@app.get("/", tags=["Root"])
def read_root() -> dict[str, str]:
    return {
        "name": "Customer Support Agent API",
        "version": "0.1.0",
        "status": "ok",
    }
