import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.db.session import get_engine, wait_for_database
from app.modules.categories.presentation.router import (
    router as categories_router,
)
from app.modules.customers.presentation.router import (
    router as customers_router,
)
from app.modules.documents.presentation.router import (
    router as documents_router,
)
from app.modules.health.presentation.router import (
    router as health_router,
)
from app.modules.orders.presentation.router import (
    router as orders_router,
)
from app.modules.products.presentation.router import (
    router as products_router,
)
from app.modules.promotions.presentation.router import (
    router as promotions_router,
)
from app.presentation.exception_handlers import (
    register_exception_handlers,
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

register_exception_handlers(app)

app.include_router(health_router)
app.include_router(documents_router)
app.include_router(categories_router)
app.include_router(products_router)
app.include_router(customers_router)
app.include_router(orders_router)
app.include_router(promotions_router)


@app.get("/", tags=["Root"])
def read_root() -> dict[str, str]:
    return {
        "name": "Customer Support Agent API",
        "version": "0.1.0",
        "status": "ok",
    }
