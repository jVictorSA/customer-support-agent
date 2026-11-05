import json
from dataclasses import replace

import pytest

from app.modules.agent.application.agents import QueryRewriter
from app.modules.agent.application.grounding import GroundingValidator
from app.modules.agent.domain.chat import ChatCompletion, ChatToolCall
from app.modules.agent.domain.context import (
    AppendedMessage,
    HistoryMessage,
    ProcessingContext,
)
from app.modules.agent.application.interfaces import ChatModel
from app.modules.agent.application.orchestrator import ReActOrchestrator
from app.modules.agent.application.process_message import (
    ProcessMessageUseCase,
)
from app.modules.agent.application.prompts import (
    INTENT_SYSTEM_PROMPT,
    ORCHESTRATOR_SYSTEM_PROMPT,
    UNSAFE_REQUEST_MESSAGE,
    WRITER_SYSTEM_PROMPT,
)
from app.modules.agent.domain.settings import AgentRuntimeSettings
from app.modules.agent.application.tools import StoreToolExecutor
from app.modules.agent.application.trace_recorder import AgentTraceRecorder
from app.modules.agent.domain.intent import Intent, IntentKind
from app.modules.agent.domain.results import (
    CatalogItem,
    Citation,
    KnowledgePassage,
    OrchestratorOutcome,
    RegisteredComplaint,
    ToolResult,
    WriterAnswer,
)

CONTEXT = ProcessingContext(
    user_message_id=1,
    user_message_public_id="user-message",
    conversation_id=10,
    conversation_public_id="conversation",
    customer_id=7,
    customer_name="Lucas",
    content="Quais violões até R$1000?",
    client_message_id="client-1",
    webhook_url="http://localhost/hook",
)

CATALOG_ITEM = CatalogItem(
    product_id=81,
    name="Yamaha C40",
    category="Violões",
    price_brl=599.9,
    effective_price_brl=599.9,
    stock_quantity=12,
    status="active",
    description="Violão clássico",
)


class ScriptedChat:
    def __init__(self, responses: list[ChatCompletion]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    async def complete(self, **kwargs) -> ChatCompletion:
        self.calls.append(kwargs)
        return self.responses.pop(0)


class FakeCounter:
    def count(self, text: str) -> int:
        return max(1, len(text) // 4)


class FakeTrace:
    def __init__(self) -> None:
        self.steps = []
        self.runs = []

    async def start_run(self, **kwargs) -> int:
        self.runs.append(kwargs)
        return 1

    async def append_step(self, run_id: int, step) -> None:
        self.steps.append(step)

    async def set_run_intent(self, run_id: int, intent: str) -> None:
        self.runs.append({"intent": intent})

    async def finish_run(self, run_id: int, **kwargs) -> None:
        self.runs.append({"finish": kwargs})


class FakeContext:
    def __init__(self) -> None:
        self.completed = []
        self.failed = []
        self.enqueued = []

    async def claim(self, message_id: int):
        return CONTEXT

    async def history(self, conversation_id: int, *, limit: int):
        return [HistoryMessage(role="assistant", content="Olá!")]

    async def complete_turn(self, **kwargs):
        self.completed.append(kwargs)
        return AppendedMessage(message_id=99, public_id="assistant-message")

    async def fail(self, message_id: int, *, error_code: str) -> None:
        self.failed.append((message_id, error_code))

    async def release_for_retry(self, message_id: int) -> None:
        pass

    async def enqueue_webhook(self, assistant_message_id: int) -> None:
        self.enqueued.append(assistant_message_id)


class FakeRetriever:
    async def search(self, query: str, *, limit=None):
        return [
            KnowledgePassage(
                reference="knowledge:chunk",
                title="Trocas",
                path="/4",
                content="Trocas em até 7 dias.",
                document_name="Políticas",
            )
        ]


class FakeCatalog:
    async def search_catalog(self, **kwargs):
        return [CATALOG_ITEM]

    async def get_product(self, reference: str):
        return CATALOG_ITEM


class FakeOrders:
    async def list_orders(self, **kwargs):
        return []

    async def get_order(self, **kwargs):
        return None

    async def get_order_by_tracking(self, **kwargs):
        return None


class FakeComplaints:
    async def register(self, **kwargs):
        return RegisteredComplaint(
            public_id="complaint", status="open", category="other"
        )


def _settings() -> AgentRuntimeSettings:
    return AgentRuntimeSettings(
        max_iterations=3,
        intent_model="intent-model",
        orchestrator_model="orch-model",
        rewriter_model="rewriter-model",
        writer_model="writer-model",
    )


async def test_process_message_full_flow() -> None:
    intent_json = json.dumps(
        {
            "primary_intent": "product_search",
            "secondary_intents": [],
            "entities": {"max_price": 1000},
            "needs_knowledge": False,
            "needs_operational_data": True,
            "wants_complaint": False,
            "out_of_scope": False,
            "urgency": "normal",
            "missing_information": [],
        }
    )
    final_note = "O catálogo tem o Yamaha C40 por R$ 599,90."
    writer_json = json.dumps(
        {
            "message": "Temos o Yamaha C40 por R$ 599,90. Quer saber mais?",
            "citations": [
                {"source_type": "product", "reference": "product:81"}
            ],
            "needs_human_handoff": False,
            "follow_up_question": None,
            "confidence": "high",
        }
    )
    chat = ScriptedChat(
        [
            ChatCompletion(content=intent_json, model="intent-model"),
            ChatCompletion(
                content=None,
                tool_calls=(
                    ChatToolCall(
                        id="call-1",
                        name="search_catalog",
                        arguments={"query": "violão", "max_price": 1000},
                    ),
                ),
                model="orch-model",
            ),
            ChatCompletion(content=final_note, model="orch-model"),
            ChatCompletion(content=writer_json, model="writer-model"),
        ]
    )
    context = FakeContext()
    trace = FakeTrace()
    use_case = ProcessMessageUseCase(
        context_port=context,
        chat=chat,
        counter=FakeCounter(),
        retriever=FakeRetriever(),
        catalog=FakeCatalog(),
        orders=FakeOrders(),
        complaints=FakeComplaints(),
        traces=trace,
        settings=_settings(),
    )

    await use_case.execute(1)

    assert len(context.completed) == 1
    completed = context.completed[0]
    assert "Yamaha C40" in completed["content"]
    assert completed["metadata"]["intent"] == "product_search"
    assert completed["is_fallback"] is False
    assert context.enqueued == [99]
    assert any(run.get("finish", {}).get("status") == "completed" for run in trace.runs)
    step_names = [step.agent_name for step in trace.steps]
    assert step_names[:2] == ["intent", "orchestrator"]
    assert "response_writer" in step_names


async def test_orchestrator_stops_at_max_iterations() -> None:
    tool_call = ChatCompletion(
        content=None,
        tool_calls=(
            ChatToolCall(
                id="call-1", name="search_catalog", arguments={}
            ),
        ),
    )
    chat = ScriptedChat([tool_call, tool_call, tool_call])
    trace = FakeTrace()
    executor = StoreToolExecutor(
        rewriter=QueryRewriter(
            chat=chat, settings=_settings(), trace=AgentTraceRecorder(trace, 1)
        ),
        retriever=FakeRetriever(),
        catalog=FakeCatalog(),
        orders=FakeOrders(),
        complaints=FakeComplaints(),
        trace=AgentTraceRecorder(trace, 1),
        settings=_settings(),
    )
    orchestrator = ReActOrchestrator(
        chat=chat,
        tools=executor,
        settings=_settings(),
        trace=AgentTraceRecorder(trace, 1),
    )

    outcome = await orchestrator.run(
        context=CONTEXT,
        intent=Intent(primary_intent=IntentKind.PRODUCT_SEARCH),
        history=[],
    )

    assert outcome.max_iterations_reached is True
    assert outcome.iterations == 3


def test_grounding_rejects_invented_price() -> None:
    validator = GroundingValidator()
    outcome = OrchestratorOutcome(
        note="ok",
        tool_results=(
            ToolResult(
                ok=True,
                data={"price_brl": 599.9},
                citations=(Citation("product", "product:81"),),
            ),
        ),
    )
    errors = validator.validate(
        intent=Intent(
            primary_intent=IntentKind.PRODUCT_SEARCH,
            needs_operational_data=True,
        ),
        outcome=outcome,
        answer=WriterAnswer(
            message="Custa R$ 899,00.",
            citations=(Citation("product", "product:81"),),
        ),
    )
    assert any("não confirmado" in error for error in errors)


def test_grounding_rejects_unknown_citation() -> None:
    validator = GroundingValidator()
    errors = validator.validate(
        intent=Intent(primary_intent=IntentKind.POLICY),
        outcome=OrchestratorOutcome(note="ok"),
        answer=WriterAnswer(
            message="A política diz 7 dias.",
            citations=(Citation("knowledge", "knowledge:invented"),),
        ),
    )
    assert errors
    assert any("base de conhecimento" in error for error in errors)


def test_grounding_accepts_policy_after_rag() -> None:
    validator = GroundingValidator()
    errors = validator.validate(
        intent=Intent(primary_intent=IntentKind.POLICY),
        outcome=OrchestratorOutcome(
            note="ok",
            tool_results=(
                ToolResult(
                    ok=True,
                    data=[{"content": "Trocas em até 7 dias."}],
                    citations=(Citation("knowledge", "knowledge:chunk"),),
                    tool_name="search_store_knowledge",
                ),
            ),
        ),
        answer=WriterAnswer(
            message="Você pode solicitar a troca em até 7 dias.",
            citations=(Citation("knowledge", "knowledge:chunk"),),
        ),
    )
    assert errors == []


async def test_harmful_out_of_scope_is_refused_without_tools() -> None:
    intent_json = json.dumps(
        {
            "primary_intent": "out_of_scope",
            "secondary_intents": [],
            "entities": {},
            "needs_knowledge": False,
            "needs_operational_data": False,
            "wants_complaint": False,
            "out_of_scope": True,
            "out_of_scope_type": "harmful_or_illegal",
            "urgency": "high",
            "missing_information": [],
        }
    )
    chat = ScriptedChat(
        [ChatCompletion(content=intent_json, model="intent-model")]
    )
    context = FakeContext()
    trace = FakeTrace()
    use_case = ProcessMessageUseCase(
        context_port=context,
        chat=chat,
        counter=FakeCounter(),
        retriever=FakeRetriever(),
        catalog=FakeCatalog(),
        orders=FakeOrders(),
        complaints=FakeComplaints(),
        traces=trace,
        settings=_settings(),
    )

    await use_case.execute(1)

    assert len(chat.calls) == 1
    assert context.completed[0]["content"] == UNSAFE_REQUEST_MESSAGE
    assert [step.agent_name for step in trace.steps] == [
        "intent",
        "grounding_validator",
    ]


async def test_benign_out_of_scope_skips_orchestrator() -> None:
    intent_json = json.dumps(
        {
            "primary_intent": "out_of_scope",
            "secondary_intents": [],
            "entities": {},
            "needs_knowledge": False,
            "needs_operational_data": False,
            "wants_complaint": False,
            "out_of_scope": True,
            "out_of_scope_type": "benign_off_topic",
            "urgency": "normal",
            "missing_information": [],
        }
    )
    writer_json = json.dumps(
        {
            "message": (
                "Não consigo ajudar com receita de bolo por aqui. "
                "Mas posso ajudar com instrumentos musicais!"
            ),
            "citations": [],
            "needs_human_handoff": False,
            "follow_up_question": None,
            "confidence": "high",
        }
    )
    chat = ScriptedChat(
        [
            ChatCompletion(content=intent_json, model="intent-model"),
            ChatCompletion(content=writer_json, model="writer-model"),
        ]
    )
    context = FakeContext()
    trace = FakeTrace()
    use_case = ProcessMessageUseCase(
        context_port=context,
        chat=chat,
        counter=FakeCounter(),
        retriever=FakeRetriever(),
        catalog=FakeCatalog(),
        orders=FakeOrders(),
        complaints=FakeComplaints(),
        traces=trace,
        settings=_settings(),
    )

    await use_case.execute(1)

    assert len(chat.calls) == 2
    assert chat.calls[1].get("tools") is None
    assert "receita de bolo" in context.completed[0]["content"]
    assert "orchestrator" not in [step.agent_name for step in trace.steps]


class FakeTextToSql:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def answer(self, **kwargs):
        self.calls.append(kwargs)
        return ToolResult(
            ok=True,
            data={
                "status": "answered",
                "rows": [{"total_brl": 100.0}],
                "query_hash": "abc",
            },
            citations=(Citation("sql", "sql:abc"),),
            trace_payload={"status": "answered", "sql": "SELECT 1"},
        )


def _tool_executor(settings: AgentRuntimeSettings, gateway) -> StoreToolExecutor:
    chat = ScriptedChat([])
    return StoreToolExecutor(
        rewriter=QueryRewriter(
            chat=chat, settings=settings, trace=AgentTraceRecorder(FakeTrace(), 1)
        ),
        retriever=FakeRetriever(),
        catalog=FakeCatalog(),
        orders=FakeOrders(),
        complaints=FakeComplaints(),
        trace=AgentTraceRecorder(FakeTrace(), 1),
        settings=settings,
        text_to_sql=gateway,
    )


def test_store_policy_tools_are_exposed() -> None:
    executor = _tool_executor(_settings(), None)

    names = {
        item["function"]["name"] for item in executor.definitions
    }

    assert {
        "get_store_status",
        "check_return_eligibility",
        "calculate_payment_options",
        "estimate_shipping",
    } <= names


def test_text_to_sql_tool_is_hidden_without_gateway() -> None:
    executor = _tool_executor(
        replace(_settings(), text_to_sql_enabled=True), None
    )

    names = {
        item["function"]["name"] for item in executor.definitions
    }

    assert "text_to_sql" not in names


def test_text_to_sql_tool_is_available_with_gateway() -> None:
    executor = _tool_executor(
        replace(_settings(), text_to_sql_enabled=True), FakeTextToSql()
    )

    names = {
        item["function"]["name"] for item in executor.definitions
    }

    assert "text_to_sql" in names


async def test_text_to_sql_tool_delegates_and_traces_payload() -> None:
    gateway = FakeTextToSql()
    trace = FakeTrace()
    executor = StoreToolExecutor(
        rewriter=QueryRewriter(
            chat=ScriptedChat([]),
            settings=_settings(),
            trace=AgentTraceRecorder(trace, 1),
        ),
        retriever=FakeRetriever(),
        catalog=FakeCatalog(),
        orders=FakeOrders(),
        complaints=FakeComplaints(),
        trace=AgentTraceRecorder(trace, 1),
        settings=replace(_settings(), text_to_sql_enabled=True),
        text_to_sql=gateway,
    )
    from app.modules.agent.domain.scope import CustomerScope

    result = await executor.execute(
        name="text_to_sql",
        arguments={"question": "Quanto eu gastei?"},
        scope=CustomerScope(
            customer_id=7,
            customer_name="Lucas",
            conversation_id=10,
            message_id=1,
        ),
        history=[],
        intent=Intent(primary_intent=IntentKind.ANALYTICS),
    )

    assert result.ok is True
    assert gateway.calls
    tool_step = next(
        step for step in trace.steps if step.tool_name == "text_to_sql"
    )
    assert tool_step.output["sql"] == "SELECT 1"


def test_prompts_encode_react_and_general_out_of_scope() -> None:
    assert "Thought:" in ORCHESTRATOR_SYSTEM_PROMPT
    assert "Action" in ORCHESTRATOR_SYSTEM_PROMPT
    assert "Observation" in ORCHESTRATOR_SYSTEM_PROMPT
    assert "Final Answer" in ORCHESTRATOR_SYSTEM_PROMPT
    assert "piada" in INTENT_SYSTEM_PROMPT
    assert "receitas de bolo" in INTENT_SYSTEM_PROMPT
    assert "harmful_or_illegal" in INTENT_SYSTEM_PROMPT
    assert "harmful_or_illegal" in WRITER_SYSTEM_PROMPT
    assert "NÃO forneça instruções" in WRITER_SYSTEM_PROMPT
