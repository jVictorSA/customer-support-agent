import csv
import os
from decimal import Decimal
from pathlib import Path

import pytest

from app.infrastructure.importing.csv_importer import (
    CsvImporter,
)
from app.modules.orders.infrastructure.repository import (
    SqlAlchemyOrderRepository,
)
from app.modules.products.infrastructure.repository import (
    SqlAlchemyProductRepository,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="set RUN_INTEGRATION_TESTS=1 to run integration tests",
    ),
]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _create_fixture(source: Path) -> None:
    _write_csv(
        source / "categories.csv",
        ["category_id", "name", "description"],
        [{"category_id": 1, "name": "Violões", "description": "Violões"}],
    )
    _write_csv(
        source / "products.csv",
        [
            "product_id",
            "price_brl",
            "name",
            "category_id",
            "description",
            "stock_quantity",
            "status",
            "specs",
            "created_at",
        ],
        [
            {
                "product_id": 81,
                "price_brl": "599.90",
                "name": "Yamaha C40",
                "category_id": 1,
                "description": "Violão clássico",
                "stock_quantity": 12,
                "status": "active",
                "specs": '{"top": "Spruce"}',
                "created_at": "2021-03-15",
            }
        ],
    )
    _write_csv(
        source / "customers.csv",
        ["customer_id", "name", "phone", "email", "city"],
        [
            {
                "customer_id": 1,
                "name": "Lucas Mendes",
                "phone": "(67) 99812-3456",
                "email": "lucas@example.com",
                "city": "Campo Grande",
            }
        ],
    )
    _write_csv(
        source / "orders.csv",
        [
            "order_id",
            "customer_id",
            "order_date",
            "status",
            "total_brl",
            "payment_method",
            "tracking_code",
            "estimated_delivery",
            "notes",
        ],
        [
            {
                "order_id": 1,
                "customer_id": 1,
                "order_date": "2025-10-15",
                "status": "delivered",
                "total_brl": "599.90",
                "payment_method": "pix",
                "tracking_code": "BRAB1234567BR",
                "estimated_delivery": "2025-10-25",
                "notes": "",
            }
        ],
    )
    _write_csv(
        source / "order_items.csv",
        ["order_id", "quantity", "product_id"],
        [{"order_id": 1, "quantity": 1, "product_id": 81}],
    )
    _write_csv(
        source / "promotions.csv",
        [
            "promotion_id",
            "product_id",
            "discount_percent",
            "description",
            "is_active",
        ],
        [
            {
                "promotion_id": 1,
                "product_id": 81,
                "discount_percent": 10,
                "description": "Black Friday",
                "is_active": 1,
            }
        ],
    )


async def test_csv_importer_is_idempotent(
    integration_session, tmp_path: Path
) -> None:
    _create_fixture(tmp_path)
    source = tmp_path

    first = await CsvImporter().import_directory(source, truncate=True)
    second = await CsvImporter().import_directory(source)

    assert first == {
        "categories": 1,
        "products": 1,
        "customers": 1,
        "orders": 1,
        "order_items": 1,
        "promotions": 1,
    }
    assert second == first

    product_repo = SqlAlchemyProductRepository(integration_session)
    product = await product_repo.get_by_id(81)
    assert product is not None
    assert product.price_brl == Decimal("599.90")

    order_repo = SqlAlchemyOrderRepository(integration_session)
    order = await order_repo.get_by_id(1)
    assert order is not None
    assert order.items[0].product_name == "Yamaha C40"
