from app.modules.agent.domain.context import HistoryMessage
from app.modules.agent.domain.scope import CustomerScope
from app.modules.agent.infrastructure.tools.text_to_sql import (
    TextToSqlToolAdapter,
)
from app.modules.agent.application.grounding import GroundingValidator
from app.modules.agent.domain.intent import Intent, IntentKind
from app.modules.agent.domain.results import (
    Citation,
    OrchestratorOutcome,
    ToolResult,
    WriterAnswer,
)
from app.modules.text_to_sql.domain.results import (
    TextToSqlOutcome,
    TextToSqlStatus,
)


class FakeUseCase:
    def __init__(self, outcome: TextToSqlOutcome) -> None:
        self.outcome = outcome
        self.requests = []

    async def execute(self, request):
        self.requests.append(request)
        return self.outcome


def _scope() -> CustomerScope:
    return CustomerScope(
        customer_id=7,
        customer_name="Lucas",
        conversation_id=10,
        message_id=1,
    )


async def test_adapter_maps_answered_outcome_without_sql() -> None:
    outcome = TextToSqlOutcome(
        status=TextToSqlStatus.ANSWERED,
        metric_id="my_total_spent",
        columns=("total_brl", "order_count"),
        rows=({"total_brl": 1234.5, "order_count": 3},),
        row_count=1,
        summary="Resultado: total_brl=1234.50; order_count=3.",
        sql="SELECT SUM(total_brl) FROM orders",
        query_hash="abc123",
        attempts=1,
        trace_output={
            "status": "answered",
            "sql": "SELECT SUM(total_brl) FROM orders",
            "rows": [{"total_brl": 1234.5, "order_count": 3}],
        },
    )
    adapter = TextToSqlToolAdapter(FakeUseCase(outcome))

    result = await adapter.answer(
        question="Quanto eu gastei?",
        history=[HistoryMessage(role="user", content="Oi")],
        scope=_scope(),
    )

    assert result.ok is True
    assert result.data["status"] == "answered"
    assert result.data["rows"] == [
        {"total_brl": 1234.5, "order_count": 3}
    ]
    assert "sql" not in result.data
    assert result.citations[0].reference == "sql:abc123"
    assert result.trace_payload is not None
    assert "SELECT" in result.trace_payload["sql"]


async def test_adapter_maps_clarification_as_ok() -> None:
    outcome = TextToSqlOutcome(
        status=TextToSqlStatus.CLARIFICATION_REQUIRED,
        question="Qual período?",
        trace_output={"status": "clarification_required"},
    )
    adapter = TextToSqlToolAdapter(FakeUseCase(outcome))

    result = await adapter.answer(
        question="E os cancelados?",
        history=[],
        scope=_scope(),
    )

    assert result.ok is True
    assert result.data["status"] == "clarification_required"
    assert result.data["question"] == "Qual período?"


def test_grounding_requires_sql_for_analytics() -> None:
    validator = GroundingValidator()
    errors = validator.validate(
        intent=Intent(
            primary_intent=IntentKind.ANALYTICS,
            needs_operational_data=True,
        ),
        outcome=OrchestratorOutcome(note="ok"),
        answer=WriterAnswer(message="Você gastou R$ 100,00."),
    )

    assert any("analítica" in error for error in errors)


def test_grounding_requires_sql_citation_for_analytics() -> None:
    validator = GroundingValidator()
    errors = validator.validate(
        intent=Intent(
            primary_intent=IntentKind.ANALYTICS,
            needs_operational_data=True,
        ),
        outcome=OrchestratorOutcome(
            note="ok",
            tool_results=(
                ToolResult(
                    ok=True,
                    data={
                        "status": "answered",
                        "rows": [{"total_brl": 100.0}],
                    },
                    citations=(Citation("sql", "sql:abc"),),
                    tool_name="text_to_sql",
                ),
            ),
        ),
        answer=WriterAnswer(message="Você gastou R$ 100,00."),
    )

    assert any("citar o resultado SQL" in error for error in errors)


def test_grounding_accepts_sql_citation_for_analytics() -> None:
    validator = GroundingValidator()
    errors = validator.validate(
        intent=Intent(
            primary_intent=IntentKind.ANALYTICS,
            needs_operational_data=True,
        ),
        outcome=OrchestratorOutcome(
            note="ok",
            tool_results=(
                ToolResult(
                    ok=True,
                    data={
                        "status": "answered",
                        "rows": [{"total_brl": 100.0}],
                    },
                    citations=(Citation("sql", "sql:abc"),),
                    tool_name="text_to_sql",
                ),
            ),
        ),
        answer=WriterAnswer(
            message="Você gastou R$ 100,00.",
            citations=(Citation("sql", "sql:abc"),),
        ),
    )

    assert errors == []
