import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.modules.text_to_sql.domain.results import (
    SqlExecutionFailure,
    SqlQueryResult,
)
from app.modules.text_to_sql.domain.settings import TextToSqlSettings

logger = logging.getLogger(__name__)


class SqlAlchemyReadOnlyExecutor:
    """Execute validated SQL through a dedicated read-only connection."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def execute(
        self,
        *,
        sql: str,
        customer_id: int,
        settings: TextToSqlSettings,
    ) -> SqlQueryResult:
        try:
            async with AsyncSession(self._engine) as session:
                async with session.begin():
                    connection = await session.connection()
                    await connection.exec_driver_sql(
                        "SET TRANSACTION READ ONLY"
                    )
                    await session.execute(
                        text(
                            "SELECT set_config("
                            "'app.customer_id', :customer_id, true)"
                        ),
                        {"customer_id": str(customer_id)},
                    )
                    await session.execute(
                        text(
                            "SELECT set_config("
                            "'statement_timeout', :timeout, true)"
                        ),
                        {"timeout": str(settings.statement_timeout_ms)},
                    )
                    result = await connection.exec_driver_sql(sql)
                    columns = tuple(str(key) for key in result.keys())
                    raw_rows = result.mappings().all()
        except Exception as exc:
            code = _error_code(exc)
            logger.warning(
                "Text-to-SQL execution failed with code %s", code
            )
            raise SqlExecutionFailure(
                code, _error_message(code)
            ) from exc

        rows = tuple(
            {str(key): _json_value(value) for key, value in row.items()}
            for row in raw_rows
        )
        return SqlQueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=len(rows) >= settings.max_rows,
        )


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return str(value)


def _error_code(exc: Exception) -> str:
    sqlstate = getattr(exc, "sqlstate", None)
    if sqlstate is None:
        orig = getattr(exc, "orig", None)
        sqlstate = getattr(orig, "sqlstate", None)
    if sqlstate == "57014":
        return "sql_timeout"
    if sqlstate == "42501":
        return "sql_not_authorized"
    if sqlstate in {"42P01", "42703", "42601", "42804"}:
        return "sql_invalid_query"
    if isinstance(exc, TimeoutError):
        return "sql_timeout"
    return "sql_execution_failed"


def _error_message(code: str) -> str:
    return {
        "sql_timeout": "A consulta excedeu o tempo limite.",
        "sql_not_authorized": "A consulta não foi autorizada.",
        "sql_invalid_query": "A consulta SQL não é válida.",
        "sql_execution_failed": "Não foi possível executar a consulta.",
    }.get(code, "Não foi possível executar a consulta.")
