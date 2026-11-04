import os
from datetime import UTC, datetime
from decimal import Decimal

import pytest

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
from app.modules.orders.domain.payment_method import (
    PaymentMethod,
)
from app.modules.orders.infrastructure.repository import (
    SqlAlchemyOrderRepository,
)
from app.modules.products.domain.product import Product
from app.modules.products.domain.product_status import (
    ProductStatus,
)
from app.modules.products.infrastructure.repository import (
    SqlAlchemyProductRepository,
)
from app.modules.promotions.domain.promotion import Promotion
from app.modules.promotions.infrastructure.repository import (
    SqlAlchemyPromotionRepository,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="set RUN_INTEGRATION_TESTS=1 to run integration tests",
    ),
]


async def test_repositories_crud_and_relations(integration_session) -> None:
    session = integration_session
    category_repo = SqlAlchemyCategoryRepository(session)
    product_repo = SqlAlchemyProductRepository(session)
    customer_repo = SqlAlchemyCustomerRepository(session)
    order_repo = SqlAlchemyOrderRepository(session)
    promotion_repo = SqlAlchemyPromotionRepository(session)

    category = await category_repo.create(
        Category(
            category_id=None,
            name="Guitarras",
            description="Guitarras elétricas",
        )
    )
    assert category.category_id is not None

    product = await product_repo.create(
        Product(
            product_id=None,
            price_brl=Decimal("599.90"),
            name="Yamaha C40",
            category_id=category.category_id,
            description="Violão clássico",
            stock_quantity=12,
            status=ProductStatus.ACTIVE,
            specs={"top": "Spruce"},
        )
    )
    second_product = await product_repo.create(
        Product(
            product_id=None,
            price_brl=Decimal("1000.00"),
            name="Yamaha C70",
            category_id=category.category_id,
            description=None,
            stock_quantity=5,
            status=ProductStatus.ACTIVE,
            specs={},
        )
    )

    loaded = await product_repo.get_by_id(product.product_id)
    assert loaded is not None
    assert loaded.price_brl == Decimal("599.90")

    products, total = await product_repo.list(
        offset=0,
        limit=10,
        category_id=category.category_id,
        status=ProductStatus.ACTIVE,
        name="yamaha",
        max_price=Decimal("700"),
    )
    assert total == 1
    assert products[0].product_id == product.product_id

    updated = await product_repo.update(
        Product(
            product_id=product.product_id,
            price_brl=Decimal("650.00"),
            name=product.name,
            category_id=product.category_id,
            description=product.description,
            stock_quantity=10,
            status=ProductStatus.ACTIVE,
            specs=product.specs,
        )
    )
    assert updated.price_brl == Decimal("650.00")

    customer = await customer_repo.create(
        Customer(
            customer_id=None,
            name="Lucas Mendes",
            phone="(67) 99812-3456",
            email="lucas@example.com",
            city="Campo Grande",
        )
    )

    promotion = await promotion_repo.create(
        Promotion(
            promotion_id=None,
            product_id=product.product_id,
            discount_percent=10,
            description="Black Friday",
            is_active=True,
        )
    )
    assert promotion.promotion_id is not None

    promotions, promotion_total = await promotion_repo.list(
        offset=0,
        limit=10,
        product_id=product.product_id,
        is_active=True,
    )
    assert promotion_total == 1
    assert promotions[0].discount_percent == 10

    order = await order_repo.create(
        Order(
            order_id=None,
            customer_id=customer.customer_id,
            order_date=datetime(2026, 1, 1, tzinfo=UTC),
            status=OrderStatus.PENDING,
            total_brl=Decimal("650.00"),
            payment_method=PaymentMethod.PIX,
            tracking_code=None,
            estimated_delivery=None,
            notes=None,
            items=(OrderItem(product_id=product.product_id, quantity=1),),
        )
    )
    assert order.order_id is not None
    assert order.items[0].product_name == "Yamaha C40"

    loaded_order = await order_repo.get_by_id(order.order_id)
    assert loaded_order is not None
    assert loaded_order.items[0].product_id == product.product_id

    orders, order_total = await order_repo.list(
        offset=0,
        limit=10,
        customer_id=customer.customer_id,
        status=OrderStatus.PENDING,
    )
    assert order_total == 1
    assert orders[0].order_id == order.order_id

    updated_order = await order_repo.update(
        Order(
            order_id=order.order_id,
            customer_id=customer.customer_id,
            order_date=order.order_date,
            status=OrderStatus.CONFIRMED,
            total_brl=Decimal("1650.00"),
            payment_method=PaymentMethod.PIX,
            tracking_code=order.tracking_code,
            estimated_delivery=order.estimated_delivery,
            notes=order.notes,
            items=(
                OrderItem(product_id=product.product_id, quantity=1),
                OrderItem(
                    product_id=second_product.product_id, quantity=1
                ),
            ),
        )
    )
    assert updated_order.status == OrderStatus.CONFIRMED
    assert len(updated_order.items) == 2

    assert await order_repo.delete(order.order_id) is True
    assert await order_repo.get_by_id(order.order_id) is None

    assert await promotion_repo.delete(promotion.promotion_id) is True
    assert await product_repo.delete(second_product.product_id) is True
    assert await product_repo.delete(product.product_id) is True
    assert await customer_repo.delete(customer.customer_id) is True
    assert await category_repo.delete(category.category_id) is True
