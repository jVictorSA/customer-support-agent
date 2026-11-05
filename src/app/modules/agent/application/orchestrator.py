import json
import time
from typing import Any

from app.modules.agent.application.interfaces import ChatModel
from app.modules.agent.domain.context import HistoryMessage, ProcessingContext
from app.modules.agent.application.prompts import ORCHESTRATOR_SYSTEM_PROMPT
from app.modules.agent.domain.settings import AgentRuntimeSettings
from app.modules.agent.domain.scope import CustomerScope
from app.modules.agent.application.tools import StoreToolExecutor
from app.modules.agent.application.trace_recorder import (
    AgentTraceRecorder,
    elapsed_ms,
)
from app.modules.agent.domain.intent import Intent
from app.modules.agent.domain.results import (
    OrchestratorOutcome,
    ToolResult,
)


class ReActOrchestrator:
    def __init__(
        self,
        *,
        chat: ChatModel,
        tools: StoreToolExecutor,
        settings: AgentRuntimeSettings,
        trace: AgentTraceRecorder,
    ) -> None:
        self._chat = chat
        self._tools = tools
        self._settings = settings
        self._trace = trace

    async def run(
        self,
        *,
        context: ProcessingContext,
        intent: Intent,
        history: list[HistoryMessage],
    ) -> OrchestratorOutcome:
        scope = CustomerScope(
            customer_id=context.customer_id,
            customer_name=context.customer_name,
            conversation_id=context.conversation_id,
            message_id=context.user_message_id,
        )
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": ORCHESTRATOR_SYSTEM_PROMPT}
        ]
        if not self._settings.text_to_sql_enabled:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "A ferramenta text_to_sql está desabilitada neste "
                        "ambiente. Use search_catalog, get_product_details, "
                        "list_my_orders, get_order_status e "
                        "search_store_knowledge."
                    ),
                }
            )
        for item in history[-self._settings.history_max_messages :]:
            messages.append({"role": item.role, "content": item.content})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"Cliente: {context.customer_name}\n"
                    f"Mensagem atual: {context.content}\n"
                    f"Intenção: {json.dumps(_intent_payload(intent), ensure_ascii=False)}\n"
                    "Decida a próxima ação. Use ferramentas quando necessário."
                ),
            }
        )

        results: list[ToolResult] = []
        note = ""
        for iteration in range(1, self._settings.max_iterations + 1):
            started = time.monotonic()
            completion = await self._chat.complete(
                messages=messages,
                tools=self._tools.definitions,
                temperature=self._settings.orchestrator_temperature,
                max_tokens=self._settings.orchestrator_max_tokens,
                model=self._settings.orchestrator_model,
            )
            await self._trace.llm_step(
                agent_name="orchestrator",
                model=completion.model or self._settings.orchestrator_model,
                messages=messages,
                completion=completion,
                temperature=self._settings.orchestrator_temperature,
                max_tokens=self._settings.orchestrator_max_tokens,
                latency_ms=elapsed_ms(started),
            )
            note = (completion.content or "").strip()

            if not completion.tool_calls:
                return OrchestratorOutcome(
                    note=note,
                    tool_results=tuple(results),
                    iterations=iteration,
                )

            messages.append(completion.assistant_message)
            for call in completion.tool_calls:
                result = await self._tools.execute(
                    name=call.name,
                    arguments=call.arguments,
                    scope=scope,
                    history=history,
                    intent=intent,
                )
                results.append(result)
                payload = json.dumps(
                    result.to_payload(),
                    ensure_ascii=False,
                    default=str,
                )[: self._settings.tool_result_max_chars]
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": call.name,
                        "content": payload,
                    }
                )

        return OrchestratorOutcome(
            note=note or "Limite de iterações atingido.",
            tool_results=tuple(results),
            iterations=self._settings.max_iterations,
            max_iterations_reached=True,
        )


def _intent_payload(intent: Intent) -> dict[str, Any]:
    return {
        "primary_intent": intent.primary_intent.value,
        "secondary_intents": [
            item.value for item in intent.secondary_intents
        ],
        "entities": intent.entities,
        "needs_knowledge": intent.needs_knowledge,
        "needs_operational_data": intent.needs_operational_data,
        "wants_complaint": intent.wants_complaint,
        "out_of_scope": intent.out_of_scope,
        "out_of_scope_type": intent.out_of_scope_type,
        "urgency": intent.urgency,
        "missing_information": list(intent.missing_information),
    }
