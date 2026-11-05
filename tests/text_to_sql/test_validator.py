import pytest

from app.modules.text_to_sql.domain.catalog import CATALOG
from app.modules.text_to_sql.domain.settings import TextToSqlSettings
from app.modules.text_to_sql.infrastructure.sql.validator import (
    SqlGlotValidator,
)


def _settings(**overrides) -> TextToSqlSettings:
    values = {"model": "test-model", "max_rows": 50}
    values.update(overrides)
    return TextToSqlSettings(**values)


def _validate(sql: str, **settings):
    return SqlGlotValidator().validate(
        sql, catalog=CATALOG, settings=_settings(**settings)
    )


def test_accepts_simple_select_and_applies_limit() -> None:
    result = _validate("SELECT name, price_brl FROM products")

    assert result.ok is True
    assert result.normalized_sql is not None
    assert result.normalized_sql.endswith("LIMIT 50")
    assert "products" in result.tables_used


def test_does_not_limit_scalar_aggregate() -> None:
    result = _validate("SELECT COUNT(*) FROM orders")

    assert result.ok is True
    assert result.normalized_sql is not None
    assert "LIMIT" not in result.normalized_sql


def test_applies_limit_to_grouped_aggregate() -> None:
    result = _validate(
        "SELECT status, COUNT(*) FROM orders GROUP BY status"
    )

    assert result.ok is True
    assert result.normalized_sql is not None
    assert result.normalized_sql.endswith("LIMIT 50")


def test_caps_existing_limit() -> None:
    result = _validate("SELECT name FROM products LIMIT 500")

    assert result.ok is True
    assert result.normalized_sql is not None
    assert result.normalized_sql.endswith("LIMIT 50")


def test_keeps_smaller_limit() -> None:
    result = _validate("SELECT name FROM products LIMIT 5")

    assert result.ok is True
    assert result.normalized_sql is not None
    assert result.normalized_sql.endswith("LIMIT 5")


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM products",
        "SELECT p.* FROM products p",
        "SELECT customer_id FROM orders",
        "SELECT notes FROM orders",
        "SELECT name FROM customers",
        "SELECT name FROM documents",
        "SELECT 1 FROM pg_catalog.pg_tables",
        "SELECT pg_sleep(5)",
        "SELECT set_config('app.customer_id', '1', true)",
        "INSERT INTO products (name) VALUES ('x')",
        "UPDATE products SET name = 'x'",
        "DELETE FROM products",
        "DROP TABLE products",
        "SELECT 1; SELECT 2",
        "SELECT name INTO new_table FROM products",
        "SELECT name FROM products FOR UPDATE",
    ],
)
def test_rejects_policy_violations(sql: str) -> None:
    result = _validate(sql)

    assert result.ok is False
    assert result.normalized_sql is None
    assert result.issues
    assert all(not issue.repairable for issue in result.issues)


def test_rejects_too_many_joins() -> None:
    sql = (
        "SELECT p.name FROM products p "
        "JOIN categories c ON c.category_id = p.category_id "
        "JOIN promotions pr ON pr.product_id = p.product_id "
        "JOIN order_items oi ON oi.product_id = p.product_id "
        "JOIN orders o ON o.order_id = oi.order_id "
        "JOIN categories c2 ON c2.category_id = p.category_id"
    )
    result = _validate(sql, max_joins=4)

    assert result.ok is False
    assert any(issue.code == "too_many_joins" for issue in result.issues)


def test_rejects_cross_join() -> None:
    result = _validate("SELECT p.name FROM products p, categories c")

    assert result.ok is False
    assert any(issue.code == "cross_join" for issue in result.issues)


def test_rejects_data_modifying_cte() -> None:
    result = _validate(
        "WITH x AS (DELETE FROM orders RETURNING order_id) "
        "SELECT order_id FROM x"
    )

    assert result.ok is False
    assert any(issue.code == "not_select" for issue in result.issues)


def test_rejects_recursive_cte() -> None:
    result = _validate(
        "WITH RECURSIVE x AS (SELECT 1 AS n) SELECT n FROM x"
    )

    assert result.ok is False
    assert any(issue.code == "recursive_cte" for issue in result.issues)


def test_allows_json_specs_extraction() -> None:
    result = _validate(
        "SELECT specs->>'color' AS color FROM products "
        "WHERE specs->>'color' ILIKE '%natural%'"
    )

    assert result.ok is True
    assert result.normalized_sql is not None


def test_allows_explicit_join_and_qualified_columns() -> None:
    result = _validate(
        "SELECT p.name, c.name FROM products p "
        "JOIN categories c ON c.category_id = p.category_id"
    )

    assert result.ok is True
    assert result.normalized_sql is not None


def test_marks_syntax_errors_repairable() -> None:
    result = _validate("SELECT FROM")

    assert result.ok is False
    assert result.issues
    assert any(issue.repairable for issue in result.issues)
