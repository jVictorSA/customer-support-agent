"""enable text-to-sql row level security and read-only grants

Revision ID: a7b8c9d0e1f2
Revises: f1a2b3c4d5e6
Create Date: 2026-11-04 22:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_READER_ROLE = "text_to_sql_reader"
_ALLOWED_TABLES = "categories, products, promotions, orders, order_items"


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_roles WHERE rolname = '{_READER_ROLE}'
            ) THEN
                RAISE EXCEPTION
                    'role {_READER_ROLE} must exist before this migration; '
                    'create it with the deploy/init script first';
            END IF;
        END
        $$;
        """
    )

    op.execute("ALTER TABLE orders ENABLE ROW LEVEL SECURITY")
    op.execute(
        "ALTER TABLE order_items ENABLE ROW LEVEL SECURITY"
    )

    op.execute(
        """
        CREATE POLICY orders_customer_isolation
        ON orders
        FOR SELECT
        USING (
            customer_id = current_setting('app.customer_id', true)::int
        )
        """
    )
    op.execute(
        """
        CREATE POLICY order_items_customer_isolation
        ON order_items
        FOR SELECT
        USING (
            EXISTS (
                SELECT 1
                FROM orders AS scoped_orders
                WHERE scoped_orders.order_id = order_items.order_id
                  AND scoped_orders.customer_id =
                      current_setting('app.customer_id', true)::int
            )
        )
        """
    )

    op.execute(f"GRANT USAGE ON SCHEMA public TO {_READER_ROLE}")
    op.execute(
        f"GRANT SELECT ON TABLE {_ALLOWED_TABLES} TO {_READER_ROLE}"
    )


def downgrade() -> None:
    op.execute(
        f"REVOKE SELECT ON TABLE {_ALLOWED_TABLES} FROM {_READER_ROLE}"
    )
    op.execute("DROP POLICY order_items_customer_isolation ON order_items")
    op.execute("DROP POLICY orders_customer_isolation ON orders")
    op.execute("ALTER TABLE order_items DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE orders DISABLE ROW LEVEL SECURITY")
