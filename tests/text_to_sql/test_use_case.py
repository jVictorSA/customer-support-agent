import json
from dataclasses import dataclass

import pytest

from app.modules.text_to_sql.application.answer import TextToSqlUseCase
from app.modules.text_to_sql.domain.catalog import CATALOG
from app.modules.text_to_sql.domain.results import (
    SqlExecutionFailure,
    SqlQueryResult,
    TextToSqlRequest,
    TextToSqlStatus,
)
from app.modules.text_to_sql.domain.settings import TextToSqlSettings
from app.modules.text_to_sql.infrastructure.sql.metrics import (
    SqlMetricBuilder,
)
from app.modules.text_to_sql.infrastructure.sql.validator import (
    SqlGlotValidator,
)


@dataclass
class Completion:
    content: str | None


class ScriptedChat:
    def __init__(self, responses: list[Completion]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    async def complete(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class FakeExecutor:
    def __init__(
        self,
        *,
        rows: tuple[dict, ...] = ({"total_brl": 1234.5, "order_count": 3},),
        failure: Exception | None = None,
    ) -> None:
        self.rows = rows
        self.failure = failure
        self.calls: list[dict] = []

    async def execute(self, **kwargs) -> SqlQueryResult:
        self.calls.append(kwargs)
        if self.failure is not None:
            raise self.failure
        return SqlQueryResult(
            columns=tuple(self.rows[0].keys()) if self.rows else (),
            rows=self.rows,
            row_count=len(self.rows),
            truncated=False,
        )


def _settings() -> TextToSqlSettings:
    return TextToSqlSettings(
        model="test-model",
        max_attempts=2,
        max_rows=50,
        writer_rows=20,
    )


def _request(question: str = "Quanto eu gastei?") -> TextToSqlRequest:
    return TextToSqlRequest(question=question, customer_id=7)


def _rewrite() -> Completion:
    return Completion(
        content=json.dumps({"standalone_question": "Quanto eu gastei?"})
    )


def _generation(**payload) -> Completion:
    base = {
        "status": "sql",
        "metric_id": None,
        "sql": None,
        "explanation": "",
        "tables_used": [],
        "columns_used": [],
        "clarification_question": None,
    }
    base.update(payload)
    return Completion(content=json.dumps(base))


def _use_case(chat, executor=None) -> TextToSqlUseCase:
    return TextToSqlUseCase(
        chat=chat,
        validator=SqlGlotValidator(),
        executor=executor or FakeExecutor(),
        metrics=SqlMetricBuilder(),
        catalog=CATALOG,
        settings=_settings(),
    )


async def test_metric_path_uses_deterministic_template() -> None:
    chat = ScriptedChat(
        [
            _rewrite(),
            _generation(status="metric", metric_id="my_total_spent"),
        ]
    )
    executor = FakeExecutor()

    outcome = await _use_case(chat, executor).execute(_request())

    assert outcome.status is TextToSqlStatus.ANSWERED
    assert outcome.metric_id == "my_total_spent"
    assert outcome.query_hash
    assert outcome.rows == ({"total_brl": 1234.5, "order_count": 3},)
    assert "1234.50" in outcome.summary
    assert executor.calls
    assert [step["agent_name"] for step in outcome.trace_output["llm_steps"]] == [
        "text_to_sql_rewriter",
        "text_to_sql_generator",
    ]


async def test_free_sql_path_executes_validated_sql() -> None:
    chat = ScriptedChat(
        [
            _rewrite(),
            _generation(sql="SELECT name, price_brl FROM products"),
        ]
    )
    executor = FakeExecutor(rows=({"name": "Yamaha C40", "price_brl": 599.9},))

    outcome = await _use_case(chat, executor).execute(_request())

    assert outcome.status is TextToSqlStatus.ANSWERED
    assert outcome.metric_id is None
    assert "Yamaha C40" in outcome.summary
    assert executor.calls[0]["sql"].endswith("LIMIT 50")


async def test_clarification_returns_question_without_execution() -> None:
    chat = ScriptedChat(
        [
            _rewrite(),
            _generation(
                status="clarification_required",
                clarification_question="Você quer os pedidos de qual período?",
            ),
        ]
    )
    executor = FakeExecutor()

    outcome = await _use_case(chat, executor).execute(_request())

    assert outcome.status is TextToSqlStatus.CLARIFICATION_REQUIRED
    assert "período" in (outcome.question or "")
    assert executor.calls == []


async def test_unsupported_returns_message_without_execution() -> None:
    chat = ScriptedChat(
        [
            _rewrite(),
            _generation(
                status="unsupported",
                explanation="Não tenho dados da loja inteira.",
            ),
        ]
    )
    executor = FakeExecutor()

    outcome = await _use_case(chat, executor).execute(_request())

    assert outcome.status is TextToSqlStatus.UNSUPPORTED
    assert "loja inteira" in (outcome.message or "")
    assert executor.calls == []


async def test_policy_violation_fails_closed_without_repair() -> None:
    chat = ScriptedChat(
        [
            _rewrite(),
            _generation(sql="SELECT customer_id FROM orders"),
        ]
    )

    outcome = await _use_case(chat).execute(_request())

    assert outcome.status is TextToSqlStatus.UNAVAILABLE
    assert outcome.error_code == "sql_policy_violation"
    assert len(chat.calls) == 2


async def test_technical_validation_error_gets_one_repair() -> None:
    chat = ScriptedChat(
        [
            _rewrite(),
            _generation(sql="SELECT unknown_column FROM products"),
            _generation(sql="SELECT name FROM products"),
        ]
    )
    executor = FakeExecutor(rows=({"name": "Yamaha C40"},))

    outcome = await _use_case(chat, executor).execute(_request())

    assert outcome.status is TextToSqlStatus.ANSWERED
    assert outcome.attempts == 2
    assert len(chat.calls) == 3
    assert executor.calls


async def test_execution_failure_is_reported_as_unavailable() -> None:
    chat = ScriptedChat(
        [
            _rewrite(),
            _generation(sql="SELECT name FROM products"),
        ]
    )
    executor = FakeExecutor(
        failure=SqlExecutionFailure(
            "sql_execution_failed", "Não foi possível executar a consulta."
        )
    )

    outcome = await _use_case(chat, executor).execute(_request())

    assert outcome.status is TextToSqlStatus.UNAVAILABLE
    assert outcome.error_code == "sql_execution_failed"


async def test_invalid_generation_json_gets_format_repair() -> None:
    chat = ScriptedChat(
        [
            _rewrite(),
            Completion(content="not json"),
            _generation(status="metric", metric_id="my_total_spent"),
        ]
    )

    outcome = await _use_case(chat).execute(_request())

    assert outcome.status is TextToSqlStatus.ANSWERED
    assert len(chat.calls) == 3
