"""create initial business tables

Revision ID: 1956eca4bb8a
Revises:
Create Date: 2026-11-04 15:54:13.214708

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "1956eca4bb8a"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

product_status = postgresql.ENUM(
    "active",
    "coming_soon",
    "discontinued",
    name="product_status",
    create_type=False,
)
order_status = postgresql.ENUM(
    "cancelled",
    "confirmed",
    "delivered",
    "pending",
    "shipped",
    name="order_status",
    create_type=False,
)
payment_method = postgresql.ENUM(
    "boleto",
    "pix",
    "debit",
    "credit_3x",
    "credit_6x",
    "credit_12x",
    name="payment_method",
    create_type=False,
)


def _timestamp_columns() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def upgrade() -> None:
    bind = op.get_bind()
    product_status.create(bind, checkfirst=True)
    order_status.create(bind, checkfirst=True)
    payment_method.create(bind, checkfirst=True)

    op.create_table(
        "categories",
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *_timestamp_columns(),
        sa.PrimaryKeyConstraint("category_id", name="pk_categories"),
    )

    op.create_table(
        "products",
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("price_brl", sa.Numeric(12, 2), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("stock_quantity", sa.Integer(), nullable=False),
        sa.Column("status", product_status, nullable=False),
        sa.Column(
            "specs",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "price_brl >= 0", name="price_brl_non_negative"
        ),
        sa.CheckConstraint(
            "stock_quantity >= 0",
            name="stock_quantity_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.category_id"],
            name="fk_products_category_id_categories",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("product_id", name="pk_products"),
    )
    op.create_index(
        "ix_products_category_id", "products", ["category_id"], unique=False
    )
    op.create_index("ix_products_status", "products", ["status"], unique=False)

    op.create_table(
        "customers",
        sa.Column(
            "customer_id",
            sa.Integer(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=120), nullable=False),
        *_timestamp_columns(),
        sa.PrimaryKeyConstraint("customer_id", name="pk_customers"),
    )

    op.create_table(
        "orders",
        sa.Column(
            "order_id",
            sa.Integer(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("order_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", order_status, nullable=False),
        sa.Column("total_brl", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_method", payment_method, nullable=False),
        sa.Column("tracking_code", sa.String(length=32), nullable=True),
        sa.Column(
            "estimated_delivery", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "total_brl >= 0", name="total_brl_non_negative"
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.customer_id"],
            name="fk_orders_customer_id_customers",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("order_id", name="pk_orders"),
    )
    op.create_index(
        "ix_orders_customer_id", "orders", ["customer_id"], unique=False
    )
    op.create_index("ix_orders_status", "orders", ["status"], unique=False)

    op.create_table(
        "order_items",
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "quantity > 0", name="quantity_positive"
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.order_id"],
            name="fk_order_items_order_id_orders",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.product_id"],
            name="fk_order_items_product_id_products",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("order_id", "product_id", name="pk_order_items"),
    )

    op.create_table(
        "promotions",
        sa.Column(
            "promotion_id",
            sa.Integer(),
            sa.Identity(always=False),
            nullable=False,
        ),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("discount_percent", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_timestamp_columns(),
        sa.CheckConstraint(
            "discount_percent BETWEEN 0 AND 100",
            name="discount_percent_range",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.product_id"],
            name="fk_promotions_product_id_products",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("promotion_id", name="pk_promotions"),
    )
    op.create_index(
        "ix_promotions_product_id",
        "promotions",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        "ix_promotions_is_active",
        "promotions",
        ["is_active"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("promotions")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("customers")
    op.drop_table("products")
    op.drop_table("categories")

    bind = op.get_bind()
    payment_method.drop(bind, checkfirst=True)
    order_status.drop(bind, checkfirst=True)
    product_status.drop(bind, checkfirst=True)
