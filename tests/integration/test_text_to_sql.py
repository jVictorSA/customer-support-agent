import os
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
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
from app.modules.text_to_sql.domain.catalog import CATALOG
from app.modules.text_to_sql.domain.results import SqlExecutionFailure
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
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="set RUN_INTEGRATION_TESTS=1 to run integration tests",
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
    customers = SqlAlchemyCustomerRepository(session)
    customer_a = await customers.create(
        Customer(
            customer_id=None,
            name="Cliente A",
            phone="(67) 99999-0001",
            email="a@example.com",
            city="Campo Grande",
        )
    )
    customer_b = await customers.create(
        Customer(
            customer_id=None,
            name="Cliente B",
            phone="(67) 99999-0002",
            email="b@example.com",
            city="Campo Grande",
        )
    )
    orders = SqlAlchemyOrderRepository(session)
    order_a = await orders.create(
        Order(
            order_id=None,
            customer_id=customer_a.customer_id,
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
    order_a2 = await orders.create(
        Order(
            order_id=None,
            customer_id=customer_a.customer_id,
            order_date=datetime(2025, 10, 2, tzinfo=UTC),
            status=OrderStatus.CANCELLED,
            total_brl=Decimal("100.00"),
            payment_method=PaymentMethod.BOLETO,
            tracking_code=None,
            estimated_delivery=None,
            notes=None,
            items=(OrderItem(product_id=product.product_id, quantity=2),),
        )
    )
    order_b = await orders.create(
        Order(
            order_id=None,
            customer_id=customer_b.customer_id,
            order_date=datetime(2025, 10, 3, tzinfo=UTC),
            status=OrderStatus.PENDING,
            total_brl=Decimal("200.00"),
            payment_method=PaymentMethod.PIX,
            tracking_code=None,
            estimated_delivery=None,
            notes=None,
            items=(OrderItem(product_id=product.product_id, quantity=1),),
        )
    )
    return customer_a, customer_b, order_a, order_a2, order_b


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


async def test_rls_limits_orders_and_order_items_to_customer(
    integration_session,
) -> None:
    session = integration_session
    customer_a, customer_b, order_a, order_a2, order_b = await _seed(session)

    async with session.begin():
        await session.execute(
            text(f"SET LOCAL ROLE {_ROLE}")
        )
        await session.execute(
            text(
                "SELECT set_config('app.customer_id', :customer_id, true)"
            ),
            {"customer_id": str(customer_a.customer_id)},
        )
        order_ids = (
            await session.execute(
                text("SELECT order_id FROM orders ORDER BY order_id")
            )
        ).scalars().all()
        item_orders = (
            await session.execute(
                text(
                    "SELECT DISTINCT order_id FROM order_items "
                    "ORDER BY order_id"
                )
            )
        ).scalars().all()

    assert set(order_ids) == {order_a.order_id, order_a2.order_id}
    assert set(item_orders) == {order_a.order_id, order_a2.order_id}
    assert order_b.order_id not in order_ids


async def test_read_only_role_cannot_write(integration_session) -> None:
    session = integration_session
    await _seed(session)

    with pytest.raises(Exception):
        async with session.begin():
            await session.execute(text(f"SET LOCAL ROLE {_ROLE}"))
            await session.execute(
                text(
                    "INSERT INTO orders "
                    "(customer_id, order_date, status, total_brl, "
                    "payment_method) "
                    "VALUES (1, now(), 'pending', 10, 'pix')"
                )
            )


async def test_read_only_role_cannot_select_internal_tables(
    integration_session,
) -> None:
    session = integration_session
    await _seed(session)

    with pytest.raises(Exception):
        async with session.begin():
            await session.execute(text(f"SET LOCAL ROLE {_ROLE}"))
            await session.execute(text("SELECT customer_id FROM customers"))


async def test_executor_applies_rls_and_statement_timeout(
    integration_session,
) -> None:
    session = integration_session
    customer_a, _, order_a, order_a2, _ = await _seed(session)
    engine = create_async_engine(_read_only_url(), poolclass=NullPool)
    executor = SqlAlchemyReadOnlyExecutor(engine)
    settings = TextToSqlSettings(
        model="test-model",
        max_rows=50,
        statement_timeout_ms=500,
    )
    try:
        result = await executor.execute(
            sql="SELECT order_id FROM orders ORDER BY order_id",
            customer_id=customer_a.customer_id,
            settings=settings,
        )
        assert set(row["order_id"] for row in result.rows) == {
            order_a.order_id,
            order_a2.order_id,
        }

        with pytest.raises(SqlExecutionFailure) as timeout:
            await executor.execute(
                sql="SELECT pg_sleep(2)",
                customer_id=customer_a.customer_id,
                settings=TextToSqlSettings(
                    model="test-model",
                    statement_timeout_ms=50,
                ),
            )
        assert timeout.value.code == "sql_timeout"
    finally:
        await engine.dispose()


async def test_metric_templates_execute_under_rls(
    integration_session,
) -> None:
    session = integration_session
    customer_a, _, _, _, _ = await _seed(session)
    engine = create_async_engine(_read_only_url(), poolclass=NullPool)
    executor = SqlAlchemyReadOnlyExecutor(engine)
    validator = SqlGlotValidator()
    metrics = SqlMetricBuilder()
    settings = TextToSqlSettings(model="test-model")
    try:
        for metric_id in CATALOG.metric_ids:
            sql = metrics.build(metric_id)
            assert sql is not None
            validation = validator.validate(
                sql, catalog=CATALOG, settings=settings
            )
            assert validation.ok, (metric_id, validation.issues)
            result = await executor.execute(
                sql=validation.normalized_sql or sql,
                customer_id=customer_a.customer_id,
                settings=settings,
            )
            assert result.row_count >= 0
    finally:
        await engine.dispose()


async def test_catalog_matches_database_columns(
    integration_session,
) -> None:
    session = integration_session
    table_names = sorted(CATALOG.table_names)
    rows = (
        await session.execute(
            text(
                "SELECT table_name, column_name "
                "FROM information_schema.columns "
                "WHERE table_schema = 'public' "
                "AND table_name = ANY(:tables)"
            ),
            {"tables": table_names},
        )
    ).all()
    actual: dict[str, set[str]] = {}
    for table_name, column_name in rows:
        actual.setdefault(table_name, set()).add(column_name)

    for table in CATALOG.tables:
        actual_columns = actual.get(table.name, set())
        assert set(table.column_names) <= actual_columns, table.name
        omitted = actual_columns - set(table.column_names)
        assert omitted <= CATALOG.denied_columns, (table.name, omitted)

    assert "customers" not in CATALOG.table_names
    assert "conversations" not in CATALOG.table_names
