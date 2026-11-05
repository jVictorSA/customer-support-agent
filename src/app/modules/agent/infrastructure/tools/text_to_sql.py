from app.modules.agent.domain.context import HistoryMessage
from app.modules.agent.domain.results import Citation, ToolResult
from app.modules.agent.domain.scope import CustomerScope
from app.modules.text_to_sql.application.answer import TextToSqlUseCase
from app.modules.text_to_sql.domain.results import (
    TextToSqlHistoryItem,
    TextToSqlRequest,
    TextToSqlStatus,
)


class TextToSqlToolAdapter:
    def __init__(self, use_case: TextToSqlUseCase) -> None:
        self._use_case = use_case

    async def answer(
        self,
        *,
        question: str,
        history: list[HistoryMessage],
        scope: CustomerScope,
    ) -> ToolResult:
        outcome = await self._use_case.execute(
            TextToSqlRequest(
                question=question,
                customer_id=scope.customer_id,
                history=tuple(
                    TextToSqlHistoryItem(role=item.role, content=item.content)
                    for item in history
                ),
            )
        )
        attempts = outcome.attempts or int(
            outcome.trace_output.get("attempts") or 0
        )
        trace_payload = {
            **outcome.trace_output,
            "status": outcome.status.value,
            "metric_id": outcome.metric_id,
            "attempts": attempts,
            "columns": list(outcome.columns),
            "row_count": outcome.row_count,
        }
        trace_payload.setdefault(
            "rows", [dict(row) for row in outcome.rows]
        )
        if outcome.error_code:
            trace_payload.setdefault("error_code", outcome.error_code)
        if outcome.sql:
            trace_payload.setdefault("sql", outcome.sql)
        if outcome.query_hash:
            trace_payload.setdefault("query_hash", outcome.query_hash)

        if outcome.status is TextToSqlStatus.ANSWERED:
            return ToolResult(
                ok=True,
                data={
                    "status": outcome.status.value,
                    "metric_id": outcome.metric_id,
                    "query_hash": outcome.query_hash,
                    "columns": list(outcome.columns),
                    "rows": [dict(row) for row in outcome.rows],
                    "row_count": outcome.row_count,
                    "truncated": outcome.truncated,
                    "summary": outcome.summary,
                },
                citations=(
                    Citation("sql", f"sql:{outcome.query_hash}"),
                ),
                trace_payload=trace_payload,
            )

        if outcome.status is TextToSqlStatus.CLARIFICATION_REQUIRED:
            return ToolResult(
                ok=True,
                data={
                    "status": outcome.status.value,
                    "question": outcome.question,
                },
                trace_payload=trace_payload,
            )

        return ToolResult(
            ok=True,
            data={
                "status": outcome.status.value,
                "message": outcome.message,
            },
            trace_payload=trace_payload,
        )
