import hashlib
import json
import logging
import time
from dataclasses import replace
from typing import Any

from app.modules.text_to_sql.application.interfaces import (
    MetricSqlBuilder,
    SqlChatModel,
    SqlExecutor,
    SqlValidator,
)
from app.modules.text_to_sql.application.prompts import (
    SQL_GENERATOR_SYSTEM_PROMPT,
    SQL_JSON_REPAIR_PROMPT,
    SQL_REPAIR_PROMPT,
    SQL_REWRITER_SYSTEM_PROMPT,
)
from app.modules.text_to_sql.application.structured import (
    coerce_generation,
    coerce_rewriter,
    parse_json_object,
)
from app.modules.text_to_sql.domain.catalog import SemanticCatalog
from app.modules.text_to_sql.domain.results import (
    SqlExecutionFailure,
    SqlGeneration,
    SqlGenerationStatus,
    SqlQueryResult,
    SqlValidationIssue,
    TextToSqlOutcome,
    TextToSqlRequest,
    TextToSqlStatus,
)
from app.modules.text_to_sql.domain.settings import TextToSqlSettings

logger = logging.getLogger(__name__)

_UNAVAILABLE_MESSAGE = (
    "Não consegui consultar esses dados agora. Tente novamente em instantes "
    "ou fale com a equipe pelo WhatsApp (67) 3341-4444."
)
_UNSUPPORTED_MESSAGE = (
    "Não tenho acesso a esse tipo de dado. Posso ajudar com catálogo, "
    "estoque, promoções e com os seus próprios pedidos."
)


class TextToSqlUseCase:
    def __init__(
        self,
        *,
        chat: SqlChatModel,
        validator: SqlValidator,
        executor: SqlExecutor,
        metrics: MetricSqlBuilder,
        catalog: SemanticCatalog,
        settings: TextToSqlSettings,
    ) -> None:
        self._chat = chat
        self._validator = validator
        self._executor = executor
        self._metrics = metrics
        self._catalog = catalog
        self._settings = settings

    async def execute(self, request: TextToSqlRequest) -> TextToSqlOutcome:
        llm_steps: list[dict[str, Any]] = []
        try:
            question = await self._rewrite(request, llm_steps)
            try:
                generation = await self._generate(
                    question, request, llm_steps
                )
            except Exception:
                logger.exception("Text-to-SQL generation failed")
                return self._finish(
                    self._unavailable(
                        "sql_generation_failed",
                        trace={"status": "unavailable"},
                    ),
                    llm_steps,
                )

            if generation.status is SqlGenerationStatus.CLARIFICATION_REQUIRED:
                return self._finish(
                    TextToSqlOutcome(
                        status=TextToSqlStatus.CLARIFICATION_REQUIRED,
                        question=generation.clarification_question,
                        attempts=1,
                        trace_output={
                            "status": "clarification_required",
                            "question": generation.clarification_question,
                        },
                    ),
                    llm_steps,
                )
            if generation.status is SqlGenerationStatus.UNSUPPORTED:
                return self._finish(
                    TextToSqlOutcome(
                        status=TextToSqlStatus.UNSUPPORTED,
                        message=generation.explanation
                        or _UNSUPPORTED_MESSAGE,
                        attempts=1,
                        trace_output={
                            "status": "unsupported",
                            "explanation": generation.explanation,
                        },
                    ),
                    llm_steps,
                )

            if generation.status is SqlGenerationStatus.METRIC:
                return self._finish(
                    await self._run_metric(generation, request),
                    llm_steps,
                )
            return self._finish(
                await self._run_sql(
                    generation.sql or "",
                    question=question,
                    request=request,
                    attempts=1,
                    llm_steps=llm_steps,
                ),
                llm_steps,
            )
        except Exception as exc:
            logger.exception("Text-to-SQL pipeline failed")
            return self._finish(
                TextToSqlOutcome(
                    status=TextToSqlStatus.UNAVAILABLE,
                    message=_UNAVAILABLE_MESSAGE,
                    error_code=type(exc).__name__,
                    trace_output={
                        "status": "unavailable",
                        "error_code": type(exc).__name__,
                    },
                ),
                llm_steps,
            )

    def _finish(
        self,
        outcome: TextToSqlOutcome,
        llm_steps: list[dict[str, Any]],
    ) -> TextToSqlOutcome:
        return replace(
            outcome,
            trace_output={
                **outcome.trace_output,
                "llm_steps": list(llm_steps),
            },
        )

    async def _rewrite(
        self,
        request: TextToSqlRequest,
        llm_steps: list[dict[str, Any]],
    ) -> str:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SQL_REWRITER_SYSTEM_PROMPT}
        ]
        for item in request.history[-6:]:
            messages.append({"role": item.role, "content": item.content})
        messages.append(
            {
                "role": "user",
                "content": f"Pergunta atual: {request.question}",
            }
        )
        try:
            started = time.monotonic()
            completion = await self._chat.complete(
                messages=messages,
                temperature=0.0,
                max_tokens=min(self._settings.max_tokens, 400),
                json_mode=True,
                model=self._settings.model,
            )
            llm_steps.append(
                _llm_step(
                    agent_name="text_to_sql_rewriter",
                    model=self._settings.model,
                    messages=messages,
                    completion=completion,
                    latency_ms=_elapsed_ms(started),
                )
            )
            return coerce_rewriter(
                parse_json_object(completion.content)
            )
        except Exception:
            logger.warning("Text-to-SQL rewriter failed; using raw question")
            return request.question

    async def _generate(
        self,
        question: str,
        request: TextToSqlRequest,
        llm_steps: list[dict[str, Any]],
    ) -> SqlGeneration:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SQL_GENERATOR_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Pergunta do cliente: "
                    f"{question}\n"
                    "O cliente autenticado só pode ver os próprios pedidos."
                ),
            },
        ]
        started = time.monotonic()
        completion = await self._chat.complete(
            messages=messages,
            temperature=self._settings.temperature,
            max_tokens=self._settings.max_tokens,
            json_mode=True,
            model=self._settings.model,
        )
        llm_steps.append(
            _llm_step(
                agent_name="text_to_sql_generator",
                model=self._settings.model,
                messages=messages,
                completion=completion,
                latency_ms=_elapsed_ms(started),
            )
        )
        try:
            return coerce_generation(parse_json_object(completion.content))
        except Exception:
            repair_messages = messages + [
                {
                    "role": "assistant",
                    "content": completion.content or "",
                },
                {
                    "role": "user",
                    "content": SQL_JSON_REPAIR_PROMPT,
                },
            ]
            started = time.monotonic()
            repaired = await self._chat.complete(
                messages=repair_messages,
                temperature=0.0,
                max_tokens=self._settings.max_tokens,
                json_mode=True,
                model=self._settings.model,
            )
            llm_steps.append(
                _llm_step(
                    agent_name="text_to_sql_generator",
                    model=self._settings.model,
                    messages=repair_messages,
                    completion=repaired,
                    latency_ms=_elapsed_ms(started),
                )
            )
            return coerce_generation(parse_json_object(repaired.content))

    async def _run_metric(
        self, generation: SqlGeneration, request: TextToSqlRequest
    ) -> TextToSqlOutcome:
        metric_id = generation.metric_id or ""
        if metric_id not in self._catalog.metric_ids:
            return self._unavailable(
                "sql_unknown_metric",
                trace={"metric_id": metric_id, "status": "unavailable"},
            )
        sql = self._metrics.build(metric_id)
        if not sql:
            return self._unavailable(
                "sql_unknown_metric",
                trace={"metric_id": metric_id, "status": "unavailable"},
            )
        validation = self._validator.validate(
            sql, catalog=self._catalog, settings=self._settings
        )
        if not validation.ok or not validation.normalized_sql:
            return self._unavailable(
                "sql_validation_failed",
                trace={
                    "metric_id": metric_id,
                    "status": "unavailable",
                    "issues": _issues_payload(validation.issues),
                },
            )
        result = await self._execute(
            validation.normalized_sql,
            request,
            metric_id=metric_id,
            attempts=1,
        )
        if isinstance(result, TextToSqlOutcome):
            return result
        return self._answered(
            result,
            sql=validation.normalized_sql,
            metric_id=metric_id,
            attempts=1,
        )

    async def _run_sql(
        self,
        sql: str,
        *,
        question: str,
        request: TextToSqlRequest,
        attempts: int,
        llm_steps: list[dict[str, Any]],
    ) -> TextToSqlOutcome:
        current_sql = sql
        current_attempt = attempts
        while True:
            validation = self._validator.validate(
                current_sql, catalog=self._catalog, settings=self._settings
            )
            if not validation.ok or not validation.normalized_sql:
                issues = validation.issues
                if any(not issue.repairable for issue in issues):
                    return self._unavailable(
                        "sql_policy_violation",
                        trace={
                            "status": "policy_violation",
                            "sql": current_sql,
                            "issues": _issues_payload(issues),
                            "attempts": current_attempt,
                        },
                    )
                if current_attempt >= self._settings.max_attempts:
                    return self._unavailable(
                        "sql_validation_failed",
                        trace={
                            "status": "validation_failed",
                            "sql": current_sql,
                            "issues": _issues_payload(issues),
                            "attempts": current_attempt,
                        },
                    )
                repaired = await self._repair(
                    question=question,
                    sql=current_sql,
                    issues=issues,
                    request=request,
                    llm_steps=llm_steps,
                )
                if repaired is None:
                    return self._unavailable(
                        "sql_validation_failed",
                        trace={
                            "status": "validation_failed",
                            "sql": current_sql,
                            "issues": _issues_payload(issues),
                            "attempts": current_attempt,
                        },
                    )
                current_sql = repaired
                current_attempt += 1
                continue

            result = await self._execute(
                validation.normalized_sql,
                request,
                attempts=current_attempt,
            )
            if isinstance(result, TextToSqlOutcome):
                if current_attempt >= self._settings.max_attempts:
                    return result
                repaired = await self._repair(
                    question=question,
                    sql=validation.normalized_sql,
                    issues=(
                        SqlValidationIssue(
                            code=result.error_code or "execution_failed",
                            message=result.message or "execution failed",
                            repairable=True,
                        ),
                    ),
                    request=request,
                    llm_steps=llm_steps,
                )
                if repaired is None:
                    return result
                current_sql = repaired
                current_attempt += 1
                continue

            return self._answered(
                result,
                sql=validation.normalized_sql,
                attempts=current_attempt,
            )

    async def _execute(
        self,
        sql: str,
        request: TextToSqlRequest,
        *,
        metric_id: str | None = None,
        attempts: int = 1,
    ) -> SqlQueryResult | TextToSqlOutcome:
        try:
            return await self._executor.execute(
                sql=sql,
                customer_id=request.customer_id,
                settings=self._settings,
            )
        except SqlExecutionFailure as exc:
            return self._unavailable(
                exc.code,
                trace={
                    "status": "execution_failed",
                    "sql": sql,
                    "metric_id": metric_id,
                    "attempts": attempts,
                    "error_code": exc.code,
                },
            )

    async def _repair(
        self,
        *,
        question: str,
        sql: str,
        issues: tuple[SqlValidationIssue, ...],
        request: TextToSqlRequest,
        llm_steps: list[dict[str, Any]],
    ) -> str | None:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SQL_GENERATOR_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Pergunta do cliente: {question}\n"
                    "O cliente autenticado só pode ver os próprios pedidos."
                ),
            },
            {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "status": "sql",
                        "sql": sql,
                        "metric_id": None,
                        "explanation": "",
                        "tables_used": [],
                        "columns_used": [],
                        "clarification_question": None,
                    },
                    ensure_ascii=False,
                ),
            },
            {
                "role": "user",
                "content": SQL_REPAIR_PROMPT.format(
                    errors="\n".join(
                        f"- {issue.code}: {issue.message}"
                        for issue in issues
                    )
                ),
            },
        ]
        try:
            started = time.monotonic()
            completion = await self._chat.complete(
                messages=messages,
                temperature=0.0,
                max_tokens=self._settings.max_tokens,
                json_mode=True,
                model=self._settings.model,
            )
            llm_steps.append(
                _llm_step(
                    agent_name="text_to_sql_repair",
                    model=self._settings.model,
                    messages=messages,
                    completion=completion,
                    latency_ms=_elapsed_ms(started),
                )
            )
            repaired = coerce_generation(
                parse_json_object(completion.content)
            )
        except Exception:
            logger.warning("Text-to-SQL repair generation failed")
            return None
        if repaired.status is not SqlGenerationStatus.SQL or not repaired.sql:
            return None
        return repaired.sql

    def _answered(
        self,
        result: SqlQueryResult,
        *,
        sql: str,
        metric_id: str | None = None,
        attempts: int = 1,
    ) -> TextToSqlOutcome:
        writer_rows = result.rows[: self._settings.writer_rows]
        truncated = result.truncated or len(result.rows) > len(writer_rows)
        query_hash = hashlib.sha256(sql.encode("utf-8")).hexdigest()[:16]
        summary = _summarize(
            columns=result.columns,
            rows=writer_rows,
            row_count=result.row_count,
            truncated=truncated,
            max_chars=self._settings.max_result_chars,
        )
        return TextToSqlOutcome(
            status=TextToSqlStatus.ANSWERED,
            metric_id=metric_id,
            columns=result.columns,
            rows=writer_rows,
            row_count=result.row_count,
            truncated=truncated,
            summary=summary,
            sql=sql,
            query_hash=query_hash,
            attempts=attempts,
            trace_output={
                "status": "answered",
                "metric_id": metric_id,
                "query_hash": query_hash,
                "sql": sql,
                "attempts": attempts,
                "columns": list(result.columns),
                "row_count": result.row_count,
                "rows": [dict(row) for row in result.rows],
            },
        )

    def _unavailable(
        self, error_code: str, *, trace: dict[str, Any]
    ) -> TextToSqlOutcome:
        return TextToSqlOutcome(
            status=TextToSqlStatus.UNAVAILABLE,
            message=_UNAVAILABLE_MESSAGE,
            error_code=error_code,
            trace_output=trace,
        )


def _issues_payload(
    issues: tuple[SqlValidationIssue, ...]
) -> list[dict[str, Any]]:
    return [
        {
            "code": issue.code,
            "message": issue.message,
            "repairable": issue.repairable,
        }
        for issue in issues
    ]


def _summarize(
    *,
    columns: tuple[str, ...],
    rows: tuple[dict[str, Any], ...],
    row_count: int,
    truncated: bool,
    max_chars: int,
) -> str:
    if not rows:
        return "Nenhum registro encontrado."
    if len(rows) == 1:
        parts = [
            f"{column}={_format_value(rows[0].get(column))}"
            for column in columns
        ]
        summary = "Resultado: " + "; ".join(parts) + "."
        return summary[:max_chars]
    preview = rows[:5]
    lines = [
        ", ".join(
            f"{column}={_format_value(row.get(column))}"
            for column in columns
        )
        for row in preview
    ]
    summary = "Primeiros resultados: " + " | ".join(lines)
    if truncated or row_count > len(preview):
        summary += (
            f" (mostrando {len(preview)} de {row_count} registros)"
        )
    return (summary + ".")[:max_chars]


def _format_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _llm_step(
    *,
    agent_name: str,
    model: str,
    messages: list[dict[str, Any]],
    completion: Any,
    latency_ms: int,
) -> dict[str, Any]:
    return {
        "agent_name": agent_name,
        "model": getattr(completion, "model", None) or model,
        "messages": messages,
        "content": getattr(completion, "content", None),
        "prompt_tokens": int(getattr(completion, "input_tokens", 0) or 0),
        "completion_tokens": int(
            getattr(completion, "output_tokens", 0) or 0
        ),
        "latency_ms": latency_ms,
    }


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
