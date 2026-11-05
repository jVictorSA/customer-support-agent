import csv
import json
import logging
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session_factory
from app.modules.categories.infrastructure.models import (
    CategoryModel,
)
from app.modules.customers.infrastructure.models import (
    CustomerModel,
)
from app.modules.orders.domain.order_status import OrderStatus
from app.modules.orders.domain.payment_method import (
    PaymentMethod,
)
from app.modules.orders.domain.sales_channel import SalesChannel
from app.modules.orders.infrastructure.models import (
    OrderItemModel,
    OrderModel,
)
from app.modules.products.domain.product_status import (
    ProductStatus,
)
from app.modules.products.infrastructure.models import (
    ProductModel,
)
from app.modules.promotions.infrastructure.models import (
    PromotionModel,
)

logger = logging.getLogger(__name__)

SEQUENCE_COLUMNS = {
    "categories": "category_id",
    "products": "product_id",
    "customers": "customer_id",
    "orders": "order_id",
    "promotions": "promotion_id",
}


class CsvImportError(ValueError):
    """Raised when an input CSV cannot be imported."""


class CsvImporter:
    """Import the six operational CSVs into an empty or existing database.

    The whole import runs in a single transaction. Rows are upserted by primary
    key, so re-running the command is safe. ``created_at`` is preserved on
    updates and ``updated_at`` is refreshed.
    """

    async def import_directory(
        self,
        source: Path,
        *,
        truncate: bool = False,
    ) -> dict[str, int]:
        if not source.is_dir():
            raise CsvImportError(f"Source directory does not exist: {source}")

        session_factory = get_session_factory()
        async with session_factory() as session:
            async with session.begin():
                if truncate:
                    await self._truncate(session)

                counts = {
                    "categories": await self._import_categories(session, source),
                    "products": await self._import_products(session, source),
                    "customers": await self._import_customers(session, source),
                    "orders": await self._import_orders(session, source),
                    "order_items": await self._import_order_items(
                        session, source
                    ),
                    "promotions": await self._import_promotions(
                        session, source
                    ),
                }

                await session.flush()
                await self._reset_sequences(session)
                return counts

    async def _truncate(self, session: AsyncSession) -> None:
        await session.execute(
            text(
                "TRUNCATE TABLE order_items, promotions, orders, products, "
                "categories, customers RESTART IDENTITY CASCADE"
            )
        )

    async def _reset_sequences(self, session: AsyncSession) -> None:
        for table, column in SEQUENCE_COLUMNS.items():
            sequence = await session.scalar(
                text("SELECT pg_get_serial_sequence(:table, :column)"),
                {"table": table, "column": column},
            )
            if sequence is None:
                continue
            await session.execute(
                text(
                    f"SELECT setval('{sequence}', "
                    f"COALESCE(MAX({column}), 0) + 1, false) FROM {table}"
                )
            )

    async def _import_categories(
        self, session: AsyncSession, source: Path
    ) -> int:
        rows = []
        for row in self._read_csv(
            source / "categories.csv", required=("category_id", "name")
        ):
            rows.append(
                {
                    "category_id": self._int(row, "category_id"),
                    "name": self._required(row, "name"),
                    "description": self._optional(row, "description"),
                    "created_at": self._timestamp(row, "created_at"),
                    "updated_at": self._timestamp(row, "updated_at"),
                }
            )
        return await self._upsert(
            session,
            CategoryModel,
            rows,
            primary_key=("category_id",),
            update_columns=("name", "description"),
        )

    async def _import_products(
        self, session: AsyncSession, source: Path
    ) -> int:
        rows = []
        for row in self._read_csv(
            source / "products.csv",
            required=(
                "product_id",
                "price_brl",
                "name",
                "category_id",
                "stock_quantity",
                "status",
            ),
        ):
            rows.append(
                {
                    "product_id": self._int(row, "product_id"),
                    "price_brl": self._decimal(row, "price_brl"),
                    "name": self._required(row, "name"),
                    "category_id": self._int(row, "category_id"),
                    "description": self._optional(row, "description"),
                    "stock_quantity": self._int(row, "stock_quantity"),
                    "status": ProductStatus(self._required(row, "status")),
                    "specs": self._json(row, "specs", default={}),
                    "created_at": self._timestamp(row, "created_at"),
                    "updated_at": self._timestamp(row, "updated_at"),
                }
            )
        return await self._upsert(
            session,
            ProductModel,
            rows,
            primary_key=("product_id",),
            update_columns=(
                "price_brl",
                "name",
                "category_id",
                "description",
                "stock_quantity",
                "status",
                "specs",
            ),
        )

    async def _import_customers(
        self, session: AsyncSession, source: Path
    ) -> int:
        rows = []
        for row in self._read_csv(
            source / "customers.csv",
            required=("customer_id", "name", "phone", "email", "city"),
        ):
            rows.append(
                {
                    "customer_id": self._int(row, "customer_id"),
                    "name": self._required(row, "name"),
                    "phone": self._required(row, "phone"),
                    "email": self._required(row, "email"),
                    "city": self._required(row, "city"),
                    "created_at": self._timestamp(row, "created_at"),
                    "updated_at": self._timestamp(row, "updated_at"),
                }
            )
        return await self._upsert(
            session,
            CustomerModel,
            rows,
            primary_key=("customer_id",),
            update_columns=("name", "phone", "email", "city"),
        )

    async def _import_orders(self, session: AsyncSession, source: Path) -> int:
        rows = []
        for row in self._read_csv(
            source / "orders.csv",
            required=(
                "order_id",
                "customer_id",
                "order_date",
                "status",
                "total_brl",
                "payment_method",
            ),
        ):
            rows.append(
                {
                    "order_id": self._int(row, "order_id"),
                    "customer_id": self._int(row, "customer_id"),
                    "order_date": self._datetime(row, "order_date"),
                    "status": OrderStatus(self._required(row, "status")),
                    "total_brl": self._decimal(row, "total_brl"),
                    "payment_method": PaymentMethod(
                        self._required(row, "payment_method")
                    ),
                    "sales_channel": self._optional_enum(
                        row, "sales_channel", SalesChannel
                    ),
                    "tracking_code": self._optional(row, "tracking_code"),
                    "estimated_delivery": self._optional_datetime(
                        row, "estimated_delivery"
                    ),
                    "delivered_at": self._optional_datetime(
                        row, "delivered_at"
                    ),
                    "notes": self._optional(row, "notes"),
                    "created_at": self._timestamp(row, "created_at"),
                    "updated_at": self._timestamp(row, "updated_at"),
                }
            )
        return await self._upsert(
            session,
            OrderModel,
            rows,
            primary_key=("order_id",),
            update_columns=(
                "customer_id",
                "order_date",
                "status",
                "total_brl",
                "payment_method",
                "sales_channel",
                "tracking_code",
                "estimated_delivery",
                "delivered_at",
                "notes",
            ),
        )

    async def _import_order_items(
        self, session: AsyncSession, source: Path
    ) -> int:
        rows = []
        for row in self._read_csv(
            source / "order_items.csv",
            required=("order_id", "quantity", "product_id"),
        ):
            rows.append(
                {
                    "order_id": self._int(row, "order_id"),
                    "quantity": self._int(row, "quantity"),
                    "product_id": self._int(row, "product_id"),
                    "is_final_sale": self._optional_bool(
                        row, "is_final_sale", default=False
                    ),
                    "is_customized": self._optional_bool(
                        row, "is_customized", default=False
                    ),
                    "is_hygiene_restricted": self._optional_bool(
                        row, "is_hygiene_restricted", default=False
                    ),
                    "created_at": self._timestamp(row, "created_at"),
                    "updated_at": self._timestamp(row, "updated_at"),
                }
            )
        return await self._upsert(
            session,
            OrderItemModel,
            rows,
            primary_key=("order_id", "product_id"),
            update_columns=(
                "quantity",
                "is_final_sale",
                "is_customized",
                "is_hygiene_restricted",
            ),
        )

    async def _import_promotions(
        self, session: AsyncSession, source: Path
    ) -> int:
        rows = []
        for row in self._read_csv(
            source / "promotions.csv",
            required=(
                "promotion_id",
                "product_id",
                "discount_percent",
                "is_active",
            ),
        ):
            rows.append(
                {
                    "promotion_id": self._int(row, "promotion_id"),
                    "product_id": self._int(row, "product_id"),
                    "discount_percent": self._int(row, "discount_percent"),
                    "description": self._optional(row, "description"),
                    "is_active": self._bool(row, "is_active"),
                    "starts_at": self._optional_datetime(row, "starts_at"),
                    "ends_at": self._optional_datetime(row, "ends_at"),
                    "created_at": self._timestamp(row, "created_at"),
                    "updated_at": self._timestamp(row, "updated_at"),
                }
            )
        return await self._upsert(
            session,
            PromotionModel,
            rows,
            primary_key=("promotion_id",),
            update_columns=(
                "product_id",
                "discount_percent",
                "description",
                "is_active",
                "starts_at",
                "ends_at",
            ),
        )

    async def _upsert(
        self,
        session: AsyncSession,
        model: type[Any],
        rows: list[dict[str, Any]],
        *,
        primary_key: tuple[str, ...],
        update_columns: tuple[str, ...],
    ) -> int:
        if not rows:
            return 0

        statement = pg_insert(model).values(rows)
        update_values = {
            column: getattr(statement.excluded, column)
            for column in update_columns
        }
        update_values["updated_at"] = func.now()
        statement = statement.on_conflict_do_update(
            index_elements=list(primary_key),
            set_=update_values,
        )
        await session.execute(statement)
        return len(rows)

    def _read_csv(
        self, path: Path, *, required: tuple[str, ...]
    ) -> list[dict[str, str]]:
        if not path.is_file():
            raise CsvImportError(f"Missing CSV file: {path}")

        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            headers = {
                header.strip() for header in (reader.fieldnames or []) if header
            }
            missing = sorted(set(required) - headers)
            if missing:
                raise CsvImportError(
                    f"{path.name} is missing required columns: "
                    f"{', '.join(missing)}"
                )
            return [
                {
                    (key or "").strip(): (value or "").strip()
                    for key, value in row.items()
                }
                for row in reader
            ]

    def _required(self, row: dict[str, str], column: str) -> str:
        value = row.get(column, "").strip()
        if not value:
            raise CsvImportError(f"Column {column!r} cannot be empty")
        return value

    def _optional(self, row: dict[str, str], column: str) -> str | None:
        value = row.get(column, "").strip()
        return value or None

    def _int(self, row: dict[str, str], column: str) -> int:
        value = self._required(row, column)
        try:
            return int(value)
        except ValueError as exc:
            raise CsvImportError(
                f"Column {column!r} must be an integer, got {value!r}"
            ) from exc

    def _decimal(self, row: dict[str, str], column: str) -> Decimal:
        value = self._required(row, column)
        try:
            return Decimal(value)
        except InvalidOperation as exc:
            raise CsvImportError(
                f"Column {column!r} must be a decimal, got {value!r}"
            ) from exc

    def _bool(self, row: dict[str, str], column: str) -> bool:
        value = self._required(row, column).lower()
        if value in {"1", "true", "t", "yes", "y"}:
            return True
        if value in {"0", "false", "f", "no", "n"}:
            return False
        raise CsvImportError(
            f"Column {column!r} must be a boolean, got {value!r}"
        )

    def _optional_bool(
        self,
        row: dict[str, str],
        column: str,
        *,
        default: bool,
    ) -> bool:
        if not row.get(column, "").strip():
            return default
        return self._bool(row, column)

    def _optional_enum(
        self,
        row: dict[str, str],
        column: str,
        enum_type: type[Any],
    ) -> Any:
        value = self._optional(row, column)
        if value is None:
            return None
        return enum_type(value)

    def _json(
        self,
        row: dict[str, str],
        column: str,
        *,
        default: dict[str, Any],
    ) -> dict[str, Any]:
        value = self._optional(row, column)
        if value is None:
            return dict(default)
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise CsvImportError(
                f"Column {column!r} must contain valid JSON"
            ) from exc
        if not isinstance(parsed, dict):
            raise CsvImportError(
                f"Column {column!r} must contain a JSON object"
            )
        return parsed

    def _datetime(self, row: dict[str, str], column: str) -> datetime:
        value = self._required(row, column)
        return self._parse_datetime(value, column)

    def _optional_datetime(
        self, row: dict[str, str], column: str
    ) -> datetime | None:
        value = self._optional(row, column)
        return self._parse_datetime(value, column) if value else None

    def _timestamp(self, row: dict[str, str], column: str) -> datetime:
        value = self._optional(row, column)
        return self._parse_datetime(value, column) if value else datetime.now(UTC)

    def _parse_datetime(self, value: str, column: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise CsvImportError(
                f"Column {column!r} must be an ISO-8601 datetime, "
                f"got {value!r}"
            ) from exc
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
