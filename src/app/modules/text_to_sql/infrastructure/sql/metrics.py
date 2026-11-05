"""Deterministic, parameterless SQL templates for recurring questions."""

_METRIC_SQL: dict[str, str] = {
    "my_total_spent": (
        "SELECT COALESCE(SUM(total_brl), 0) AS total_brl, "
        "COUNT(*) AS order_count "
        "FROM orders "
        "WHERE status <> 'cancelled'"
    ),
    "my_order_count": (
        "SELECT status, COUNT(*) AS order_count "
        "FROM orders "
        "GROUP BY status "
        "ORDER BY status"
    ),
    "my_average_order_value": (
        "SELECT COALESCE(AVG(total_brl), 0) AS average_order_value_brl, "
        "COUNT(*) AS order_count "
        "FROM orders "
        "WHERE status <> 'cancelled'"
    ),
    "my_top_products": (
        "SELECT p.name AS product_name, SUM(oi.quantity) AS quantity "
        "FROM order_items AS oi "
        "JOIN orders AS o ON o.order_id = oi.order_id "
        "JOIN products AS p ON p.product_id = oi.product_id "
        "WHERE o.status <> 'cancelled' "
        "GROUP BY p.product_id, p.name "
        "ORDER BY quantity DESC, p.name "
        "LIMIT 5"
    ),
    "catalog_availability": (
        "SELECT c.name AS category_name, "
        "COUNT(p.product_id) AS total_products, "
        "COUNT(p.product_id) FILTER (WHERE p.status = 'active') "
        "AS active_products, "
        "COUNT(p.product_id) FILTER (WHERE p.status = 'coming_soon') "
        "AS coming_soon_products, "
        "COUNT(p.product_id) FILTER (WHERE p.status = 'discontinued') "
        "AS discontinued_products, "
        "COALESCE(SUM(p.stock_quantity), 0) AS stock_units "
        "FROM categories AS c "
        "LEFT JOIN products AS p ON p.category_id = c.category_id "
        "GROUP BY c.category_id, c.name "
        "ORDER BY total_products DESC, c.name"
    ),
    "active_promotions": (
        "SELECT p.name AS product_name, pr.discount_percent, "
        "pr.description "
        "FROM promotions AS pr "
        "JOIN products AS p ON p.product_id = pr.product_id "
        "WHERE pr.is_active = TRUE AND p.status = 'active' "
        "ORDER BY pr.discount_percent DESC, p.name "
        "LIMIT 10"
    ),
}


class SqlMetricBuilder:
    def build(self, metric_id: str) -> str | None:
        return _METRIC_SQL.get(metric_id)
