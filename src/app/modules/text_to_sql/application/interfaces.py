from typing import Any, Protocol

from app.modules.text_to_sql.domain.catalog import SemanticCatalog
from app.modules.text_to_sql.domain.results import (
    SqlQueryResult,
    SqlValidationResult,
)
from app.modules.text_to_sql.domain.settings import TextToSqlSettings


class SqlChatModel(Protocol):
    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1000,
        json_mode: bool = False,
        model: str | None = None,
    ): ...


class SqlValidator(Protocol):
    def validate(
        self,
        sql: str,
        *,
        catalog: SemanticCatalog,
        settings: TextToSqlSettings,
    ) -> SqlValidationResult: ...


class SqlExecutor(Protocol):
    async def execute(
        self,
        *,
        sql: str,
        customer_id: int,
        settings: TextToSqlSettings,
    ) -> SqlQueryResult: ...


class MetricSqlBuilder(Protocol):
    def build(self, metric_id: str) -> str | None: ...
