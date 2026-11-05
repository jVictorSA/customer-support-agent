import logging
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from app.modules.text_to_sql.domain.catalog import SemanticCatalog
from app.modules.text_to_sql.domain.results import (
    SqlValidationIssue,
    SqlValidationResult,
)
from app.modules.text_to_sql.domain.settings import TextToSqlSettings

logger = logging.getLogger(__name__)

_SYSTEM_SCHEMAS = {"pg_catalog", "information_schema", "pg_toast"}
_DENIED_FUNCTIONS = {
    "pg_sleep",
    "set_config",
    "current_setting",
    "pg_read_file",
    "pg_read_binary_file",
    "pg_ls_dir",
    "pg_stat_file",
    "dblink",
    "generate_series",
    "lo_import",
    "lo_export",
}
_ALLOWED_ANONYMOUS_FUNCTIONS = {
    "count",
    "sum",
    "avg",
    "min",
    "max",
    "round",
    "coalesce",
    "nullif",
    "lower",
    "upper",
    "trim",
    "length",
    "date_trunc",
    "extract",
    "now",
    "current_date",
    "current_timestamp",
    "cast",
    "greatest",
    "least",
    "concat",
    "substring",
    "position",
    "abs",
    "ceil",
    "floor",
    "sign",
    "date_part",
    "to_char",
    "to_date",
}


class SqlGlotValidator:
    def validate(
        self,
        sql: str,
        *,
        catalog: SemanticCatalog,
        settings: TextToSqlSettings,
    ) -> SqlValidationResult:
        try:
            statements = sqlglot.parse(sql, read="postgres")
        except ParseError as exc:
            return _failure("syntax_error", _sanitize(str(exc)), repairable=True)

        if len(statements) != 1:
            return _failure(
                "multiple_statements",
                "Apenas um statement SQL é permitido.",
                repairable=False,
            )

        root = statements[0]
        if root is None:
            return _failure(
                "syntax_error", "Consulta SQL vazia.", repairable=True
            )
        if not isinstance(root, (exp.Select, exp.SetOperation)):
            return _failure(
                "not_select",
                "Apenas consultas SELECT são permitidas.",
                repairable=False,
            )

        issues: list[SqlValidationIssue] = []
        for node in root.walk():
            if isinstance(
                node,
                (
                    exp.Insert,
                    exp.Update,
                    exp.Delete,
                    exp.Create,
                    exp.Drop,
                    exp.Alter,
                    exp.Command,
                ),
            ):
                issues.append(
                    _issue(
                        "not_select",
                        "Apenas consultas SELECT são permitidas.",
                        False,
                    )
                )
                break
        cte_names = {
            cte.alias_or_name.lower()
            for cte in root.find_all(exp.CTE)
            if cte.alias_or_name
        }
        subquery_aliases = {
            subquery.alias_or_name.lower()
            for subquery in root.find_all(exp.Subquery)
            if subquery.alias_or_name
        }

        if len(cte_names) > settings.max_ctes:
            issues.append(
                _issue("too_many_ctes", "Muitas CTEs na consulta.", False)
            )

        with_expr = root.args.get("with_")
        if with_expr is not None and with_expr.args.get("recursive"):
            issues.append(
                _issue(
                    "recursive_cte",
                    "CTEs recursivas não são permitidas.",
                    False,
                )
            )

        if root.find(exp.Into):
            issues.append(
                _issue("select_into", "SELECT INTO não é permitido.", False)
            )
        if root.find(exp.Lock):
            issues.append(
                _issue(
                    "locking_clause",
                    "Cláusulas de bloqueio não são permitidas.",
                    False,
                )
            )
        if root.find(exp.Parameter):
            issues.append(
                _issue("parameter", "Parâmetros não são permitidos.", False)
            )

        if _depth(root) > settings.max_ast_depth:
            issues.append(
                _issue("too_deep", "Consulta muito complexa.", False)
            )

        joins = list(root.find_all(exp.Join))
        if len(joins) > settings.max_joins:
            issues.append(
                _issue("too_many_joins", "Muitos joins na consulta.", False)
            )
        for join in joins:
            kind = str(join.args.get("kind") or "").upper()
            if kind == "CROSS":
                issues.append(
                    _issue("cross_join", "CROSS JOIN não é permitido.", False)
                )
            if (
                not join.args.get("on")
                and not join.args.get("using")
                and kind not in {"NATURAL"}
            ):
                issues.append(
                    _issue(
                        "cross_join",
                        "Joins devem ter condição ON ou USING.",
                        False,
                    )
                )

        union_nodes = list(root.find_all(exp.Union))
        if len(union_nodes) > settings.max_union_branches:
            issues.append(
                _issue(
                    "too_many_unions", "Muitos branches de UNION.", False
                )
            )

        table_aliases: dict[str, str] = {}
        tables_used: list[str] = []
        for table in root.find_all(exp.Table):
            name = table.name.lower()
            alias = table.alias_or_name.lower()
            schema = (table.db or "").lower()
            catalog_name = (table.catalog or "").lower()

            if name in cte_names:
                table_aliases[alias] = "__cte__"
                continue
            if schema in _SYSTEM_SCHEMAS or catalog_name in _SYSTEM_SCHEMAS:
                issues.append(
                    _issue(
                        "system_catalog",
                        f"Acesso a catálogo do sistema não é permitido: {name}.",
                        False,
                    )
                )
                continue
            if schema and schema != "public":
                issues.append(
                    _issue(
                        "forbidden_table",
                        f"Schema não permitido: {schema}.",
                        False,
                    )
                )
                continue
            if name not in catalog.table_names:
                issues.append(
                    _issue(
                        "forbidden_table",
                        f"Tabela não permitida: {name}.",
                        False,
                    )
                )
                continue
            table_aliases[alias] = name
            if name not in tables_used:
                tables_used.append(name)

        for subquery in root.find_all(exp.Subquery):
            alias = subquery.alias_or_name.lower()
            if alias:
                table_aliases.setdefault(alias, "__subquery__")

        select_aliases = {
            alias.alias.lower()
            for alias in root.find_all(exp.Alias)
            if alias.alias
        }
        allowed_columns = catalog.all_allowed_columns()
        columns_used: list[str] = []

        for star in root.find_all(exp.Star):
            if isinstance(star.parent, exp.Count):
                continue
            issues.append(
                _issue("select_star", "SELECT * não é permitido.", False)
            )

        for column in root.find_all(exp.Column):
            name = (column.name or "").lower()
            if not name or name == "*":
                continue
            if name in catalog.denied_columns:
                issues.append(
                    _issue(
                        "forbidden_column",
                        f"Coluna não permitida: {column.name}.",
                        False,
                    )
                )
                continue

            qualifier = (column.table or "").lower()
            if qualifier:
                resolved = table_aliases.get(qualifier, qualifier)
                if resolved in {"__cte__", "__subquery__"}:
                    if name not in columns_used:
                        columns_used.append(name)
                    continue
                if resolved not in catalog.table_names:
                    # Derived table alias not registered; do not guess columns.
                    if name not in columns_used:
                        columns_used.append(name)
                    continue
                if name not in catalog.columns_for(resolved):
                    issues.append(
                        _issue(
                            "unknown_column",
                            f"Coluna inexistente em {resolved}: "
                            f"{column.name}.",
                            True,
                        )
                    )
                elif name not in columns_used:
                    columns_used.append(name)
                continue

            if name in select_aliases:
                continue
            if name not in allowed_columns:
                issues.append(
                    _issue(
                        "unknown_column",
                        f"Coluna inexistente: {column.name}.",
                        True,
                    )
                )
            elif name not in columns_used:
                columns_used.append(name)

        for func in root.find_all(exp.Func):
            func_name = _function_name(func)
            if func_name in _DENIED_FUNCTIONS:
                issues.append(
                    _issue(
                        "forbidden_function",
                        f"Função não permitida: {func_name}.",
                        False,
                    )
                )
            elif isinstance(func, exp.Anonymous) and (
                func_name not in _ALLOWED_ANONYMOUS_FUNCTIONS
            ):
                issues.append(
                    _issue(
                        "forbidden_function",
                        f"Função não permitida: {func_name}.",
                        False,
                    )
                )

        if issues:
            return SqlValidationResult(
                ok=False,
                normalized_sql=None,
                issues=tuple(_dedupe_issues(issues)),
                tables_used=tuple(tables_used),
                columns_used=tuple(columns_used),
            )

        normalized = _apply_limit(
            root,
            settings.max_rows,
            returns_rows=_returns_rows(root),
        )
        return SqlValidationResult(
            ok=True,
            normalized_sql=normalized.sql(dialect="postgres"),
            tables_used=tuple(tables_used),
            columns_used=tuple(columns_used),
        )


def _apply_limit(
    root: exp.Expression, max_rows: int, *, returns_rows: bool
) -> exp.Expression:
    if not returns_rows:
        return root
    existing = _literal_int(root.args.get("limit"))
    limit = min(existing, max_rows) if existing is not None else max_rows
    try:
        return root.limit(limit)
    except Exception:
        logger.exception("Could not apply SQL limit")
        return root


def _literal_int(limit: Any) -> int | None:
    if limit is None:
        return None
    expression = limit.args.get("expression") if isinstance(limit, exp.Limit) else None
    if isinstance(expression, exp.Literal) and not expression.is_string:
        try:
            return int(expression.this)
        except (TypeError, ValueError):
            return None
    return None


def _returns_rows(root: exp.Expression) -> bool:
    if isinstance(root, exp.SetOperation):
        return True
    if not isinstance(root, exp.Select):
        return True
    has_group = root.args.get("group") is not None
    has_aggregate = root.find(exp.AggFunc) is not None
    return has_group or not has_aggregate


def _depth(node: Any) -> int:
    if not isinstance(node, exp.Expression):
        return 0
    maximum = 0
    for value in node.args.values():
        if isinstance(value, exp.Expression):
            maximum = max(maximum, _depth(value))
        elif isinstance(value, list):
            for item in value:
                maximum = max(maximum, _depth(item))
    return maximum + 1


def _function_name(func: exp.Func) -> str:
    if isinstance(func, exp.Anonymous):
        return str(func.name or "").lower()
    try:
        return str(func.sql_name() or "").lower()
    except Exception:
        return type(func).__name__.lower()


def _failure(code: str, message: str, *, repairable: bool) -> SqlValidationResult:
    return SqlValidationResult(
        ok=False,
        normalized_sql=None,
        issues=(_issue(code, message, repairable),),
    )


def _issue(code: str, message: str, repairable: bool) -> SqlValidationIssue:
    return SqlValidationIssue(
        code=code, message=message, repairable=repairable
    )


def _dedupe_issues(issues: list[SqlValidationIssue]) -> list[SqlValidationIssue]:
    seen: set[tuple[str, str]] = set()
    result: list[SqlValidationIssue] = []
    for issue in issues:
        key = (issue.code, issue.message)
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)
    return result


def _sanitize(message: str) -> str:
    return " ".join(str(message).split())[:300]
