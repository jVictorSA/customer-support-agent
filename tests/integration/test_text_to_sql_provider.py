import os
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.modules.agent.infrastructure.llm.deepseek_chat import (
    DeepSeekChatClient,
)
from app.modules.categories.domain.category import Category
from app.modules.categories.infrastructure.repository import (
    SqlAlchemyCategoryRepository,
)
from app.modules.customers.domain.customer import Customer
from app.modules.customers.infrastructure.repository import (
    SqlAlchemyCustomerRepository,
)
from app.modules.orders.domain.order import Order
from app.modules.orders.domain.order_item import OrderItem
from app.modules.orders.domain.order_status import OrderStatus
from app.modules.orders.domain.payment_method import PaymentMethod
from app.modules.orders.infrastructure.repository import (
    SqlAlchemyOrderRepository,
)
from app.modules.products.domain.product import Product
from app.modules.products.domain.product_status import ProductStatus
from app.modules.products.infrastructure.repository import (
    SqlAlchemyProductRepository,
)
from app.modules.text_to_sql.application.answer import TextToSqlUseCase
from app.modules.text_to_sql.domain.catalog import CATALOG
from app.modules.text_to_sql.domain.results import (
    TextToSqlRequest,
    TextToSqlStatus,
)
from app.modules.text_to_sql.domain.settings import TextToSqlSettings
from app.modules.text_to_sql.infrastructure.sql.executor import (
    SqlAlchemyReadOnlyExecutor,
)
from app.modules.text_to_sql.infrastructure.sql.metrics import (
    SqlMetricBuilder,
)
from app.modules.text_to_sql.infrastructure.sql.validator import (
    SqlGlotValidator,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.provider,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1"
        or not os.getenv("DEEPSEEK_API_KEY"),
        reason=(
            "set RUN_INTEGRATION_TESTS=1 and DEEPSEEK_API_KEY to run "
            "provider evaluation"
        ),
    ),
]

_ROLE = "text_to_sql_reader"
_DEFAULT_PASSWORD = "dev-only-text-to-sql-password"


def _password() -> str:
    configured = get_settings().text_to_sql_db_password
    if configured is not None:
        return configured.get_secret_value()
    return os.getenv("TEXT_TO_SQL_DB_PASSWORD", _DEFAULT_PASSWORD)


async def _seed(session):
    category = await SqlAlchemyCategoryRepository(session).create(
        Category(
            category_id=None,
            name="Violões",
            description="Violões acústicos",
        )
    )
    product = await SqlAlchemyProductRepository(session).create(
        Product(
            product_id=None,
            price_brl=Decimal("599.90"),
            name="Yamaha C40",
            category_id=category.category_id,
            description="Violão clássico",
            stock_quantity=12,
            status=ProductStatus.ACTIVE,
            specs={"color": "Natural", "top": "Spruce"},
        )
    )
    customer = await SqlAlchemyCustomerRepository(session).create(
        Customer(
            customer_id=None,
            name="Cliente Provider",
            phone="(67) 99999-0010",
            email="provider@example.com",
            city="Campo Grande",
        )
    )
    await SqlAlchemyOrderRepository(session).create(
        Order(
            order_id=None,
            customer_id=customer.customer_id,
            order_date=datetime(2025, 10, 1, tzinfo=UTC),
            status=OrderStatus.DELIVERED,
            total_brl=Decimal("599.90"),
            payment_method=PaymentMethod.PIX,
            tracking_code=None,
            estimated_delivery=None,
            notes=None,
            items=(OrderItem(product_id=product.product_id, quantity=1),),
        )
    )
    return customer


def _read_only_url() -> URL:
    settings = get_settings()
    return URL.create(
        drivername="postgresql+asyncpg",
        username=_ROLE,
        password=_password(),
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
    )


def _chat() -> DeepSeekChatClient:
    settings = get_settings()
    key = (
        settings.deepseek_api_key.get_secret_value()
        if settings.deepseek_api_key
        else ""
    )
    return DeepSeekChatClient(
        api_key=key,
        base_url=settings.deepseek_base_url,
        default_model=settings.deepseek_model,
        timeout=settings.deepseek_timeout,
        max_retries=settings.deepseek_max_retries,
        disable_thinking=True,
    )


async def _outcome(question: str, customer_id: int):
    engine = create_async_engine(_read_only_url(), poolclass=NullPool)
    try:
        use_case = TextToSqlUseCase(
            chat=_chat(),
            validator=SqlGlotValidator(),
            executor=SqlAlchemyReadOnlyExecutor(engine),
            metrics=SqlMetricBuilder(),
            catalog=CATALOG,
            settings=TextToSqlSettings(
                model=get_settings().text_to_sql_model_name,
                max_attempts=2,
                max_rows=50,
                writer_rows=20,
            ),
        )
        return await use_case.execute(
            TextToSqlRequest(question=question, customer_id=customer_id)
        )
    finally:
        await engine.dispose()


def _contains_value(outcome, expected: object) -> bool:
    for row in outcome.rows:
        for value in row.values():
            if value == expected:
                return True
            if isinstance(value, (int, float)) and isinstance(
                expected, (int, float)
            ):
                if abs(float(value) - float(expected)) < 0.01:
                    return True
    return False


async def test_provider_execution_accuracy(integration_session) -> None:
    customer = await _seed(integration_session)

    total = await _outcome(
        "Quanto eu já gastei na loja?", customer.customer_id
    )
    assert total.status is TextToSqlStatus.ANSWERED, total.trace_output
    assert _contains_value(total, 599.9)

    top = await _outcome(
        "Quais produtos eu mais comprei?", customer.customer_id
    )
    assert top.status is TextToSqlStatus.ANSWERED, top.trace_output
    assert any(
        "Yamaha C40" in str(value)
        for row in top.rows
        for value in row.values()
    )
