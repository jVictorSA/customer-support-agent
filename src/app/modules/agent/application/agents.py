import json
import time
from typing import Any

from app.modules.agent.application.interfaces import ChatModel, TokenCounter
from app.modules.agent.domain.context import HistoryMessage, ProcessingContext
from app.modules.agent.application.prompts import (
    INTENT_SYSTEM_PROMPT,
    ORCHESTRATOR_SYSTEM_PROMPT,
    REPAIR_PROMPT,
    REWRITER_SYSTEM_PROMPT,
    WRITER_SYSTEM_PROMPT,
)
from app.modules.agent.domain.settings import AgentRuntimeSettings
from app.modules.agent.application.structured import (
    coerce_intent,
    coerce_rewriter,
    coerce_writer,
    parse_json_object,
)
from app.modules.agent.application.trace_recorder import (
    AgentTraceRecorder,
    elapsed_ms,
)
from app.modules.agent.domain.intent import Intent
from app.modules.agent.domain.results import (
    OrchestratorOutcome,
    WriterAnswer,
)


def _fit_history(
    history: list[HistoryMessage],
    *,
    max_messages: int,
    max_tokens: int,
    counter: TokenCounter,
) -> list[HistoryMessage]:
    selected: list[HistoryMessage] = []
    total = 0
    for message in reversed(history[-max_messages:]):
        tokens = counter.count(message.content)
        if selected and total + tokens > max_tokens:
            break
        selected.append(message)
        total += tokens
    return list(reversed(selected))


class IntentAgent:
    def __init__(
        self,
        *,
        chat: ChatModel,
        settings: AgentRuntimeSettings,
        counter: TokenCounter,
        trace: AgentTraceRecorder,
    ) -> None:
        self._chat = chat
        self._settings = settings
        self._counter = counter
        self._trace = trace

    async def identify(
        self,
        context: ProcessingContext,
        history: list[HistoryMessage],
    ) -> Intent:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": INTENT_SYSTEM_PROMPT}
        ]
        for item in _fit_history(
            history,
            max_messages=self._settings.history_max_messages,
            max_tokens=self._settings.history_max_tokens,
            counter=self._counter,
        ):
            messages.append({"role": item.role, "content": item.content})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"Cliente: {context.customer_name}\n"
                    f"Mensagem atual do cliente:\n{context.content}"
                ),
            }
        )

        started = time.monotonic()
        completion = await self._chat.complete(
            messages=messages,
            temperature=self._settings.intent_temperature,
            max_tokens=self._settings.intent_max_tokens,
            json_mode=True,
            model=self._settings.intent_model,
        )
        await self._trace.llm_step(
            agent_name="intent",
            model=completion.model or self._settings.intent_model,
            messages=messages,
            completion=completion,
            temperature=self._settings.intent_temperature,
            max_tokens=self._settings.intent_max_tokens,
            latency_ms=elapsed_ms(started),
        )
        try:
            return coerce_intent(parse_json_object(completion.content))
        except (ValueError, json.JSONDecodeError):
            repair_messages = messages + [
                {
                    "role": "assistant",
                    "content": completion.content or "",
                },
                {
                    "role": "user",
                    "content": (
                        "Sua resposta anterior não era um JSON válido. "
                        "Responda apenas com o objeto JSON solicitado."
                    ),
                },
            ]
            started = time.monotonic()
            repaired = await self._chat.complete(
                messages=repair_messages,
                temperature=0.0,
                max_tokens=self._settings.intent_max_tokens,
                json_mode=True,
                model=self._settings.intent_model,
            )
            await self._trace.llm_step(
                agent_name="intent",
                model=repaired.model or self._settings.intent_model,
                messages=repair_messages,
                completion=repaired,
                temperature=0.0,
                max_tokens=self._settings.intent_max_tokens,
                latency_ms=elapsed_ms(started),
            )
            return coerce_intent(parse_json_object(repaired.content))


class QueryRewriter:
    def __init__(
        self,
        *,
        chat: ChatModel,
        settings: AgentRuntimeSettings,
        trace: AgentTraceRecorder,
    ) -> None:
        self._chat = chat
        self._settings = settings
        self._trace = trace

    async def rewrite(
        self,
        *,
        query: str,
        history: list[HistoryMessage],
        intent: Intent,
    ) -> str:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": REWRITER_SYSTEM_PROMPT}
        ]
        for item in history[-6:]:
            messages.append({"role": item.role, "content": item.content})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"Intenção: {intent.primary_intent.value}\n"
                    f"Pergunta atual: {query}"
                ),
            }
        )
        started = time.monotonic()
        completion = await self._chat.complete(
            messages=messages,
            temperature=self._settings.rewriter_temperature,
            max_tokens=self._settings.rewriter_max_tokens,
            json_mode=True,
            model=self._settings.rewriter_model,
        )
        await self._trace.llm_step(
            agent_name="query_rewriter",
            model=completion.model or self._settings.rewriter_model,
            messages=messages,
            completion=completion,
            temperature=self._settings.rewriter_temperature,
            max_tokens=self._settings.rewriter_max_tokens,
            latency_ms=elapsed_ms(started),
        )
        try:
            return coerce_rewriter(parse_json_object(completion.content))
        except (ValueError, json.JSONDecodeError):
            return query


class ResponseWriter:
    def __init__(
        self,
        *,
        chat: ChatModel,
        settings: AgentRuntimeSettings,
        trace: AgentTraceRecorder,
    ) -> None:
        self._chat = chat
        self._settings = settings
        self._trace = trace

    async def write(
        self,
        *,
        context: ProcessingContext,
        intent: Intent,
        outcome: OrchestratorOutcome,
        history: list[HistoryMessage],
    ) -> WriterAnswer:
        messages = self._messages(
            context=context, intent=intent, outcome=outcome, history=history
        )
        started = time.monotonic()
        completion = await self._chat.complete(
            messages=messages,
            temperature=self._settings.writer_temperature,
            max_tokens=self._settings.writer_max_tokens,
            json_mode=True,
            model=self._settings.writer_model,
        )
        await self._trace.llm_step(
            agent_name="response_writer",
            model=completion.model or self._settings.writer_model,
            messages=messages,
            completion=completion,
            temperature=self._settings.writer_temperature,
            max_tokens=self._settings.writer_max_tokens,
            latency_ms=elapsed_ms(started),
        )
        return coerce_writer(parse_json_object(completion.content))

    async def repair(
        self,
        *,
        context: ProcessingContext,
        intent: Intent,
        outcome: OrchestratorOutcome,
        history: list[HistoryMessage],
        previous: WriterAnswer,
        errors: list[str],
    ) -> WriterAnswer:
        messages = self._messages(
            context=context, intent=intent, outcome=outcome, history=history
        )
        messages.extend(
            [
                {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "message": previous.message,
                            "citations": [
                                {
                                    "source_type": citation.source_type,
                                    "reference": citation.reference,
                                }
                                for citation in previous.citations
                            ],
                            "needs_human_handoff": previous.needs_human_handoff,
                            "follow_up_question": previous.follow_up_question,
                            "confidence": previous.confidence,
                        },
                        ensure_ascii=False,
                    ),
                },
                {
                    "role": "user",
                    "content": REPAIR_PROMPT.format(
                        errors="\n".join(f"- {error}" for error in errors)
                    ),
                },
            ]
        )
        started = time.monotonic()
        completion = await self._chat.complete(
            messages=messages,
            temperature=0.1,
            max_tokens=self._settings.writer_max_tokens,
            json_mode=True,
            model=self._settings.writer_model,
        )
        await self._trace.llm_step(
            agent_name="response_writer",
            model=completion.model or self._settings.writer_model,
            messages=messages,
            completion=completion,
            temperature=0.1,
            max_tokens=self._settings.writer_max_tokens,
            latency_ms=elapsed_ms(started),
        )
        return coerce_writer(parse_json_object(completion.content))

    def _messages(
        self,
        *,
        context: ProcessingContext,
        intent: Intent,
        outcome: OrchestratorOutcome,
        history: list[HistoryMessage],
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": WRITER_SYSTEM_PROMPT}
        ]
        for item in _fit_history(
            history,
            max_messages=self._settings.history_max_messages,
            max_tokens=self._settings.history_max_tokens,
            counter=_ApproxCounter(),
        ):
            messages.append({"role": item.role, "content": item.content})

        tool_payload = [
            result.to_payload() for result in outcome.tool_results
        ]
        messages.append(
            {
                "role": "user",
                "content": (
                    f"Cliente: {context.customer_name}\n"
                    f"Pergunta atual: {context.content}\n"
                    f"Intenção: {json.dumps(_intent_payload(intent), ensure_ascii=False)}\n"
                    f"Nota do orquestrador: {outcome.note}\n"
                    "Resultados das ferramentas:\n"
                    f"{json.dumps(tool_payload, ensure_ascii=False, default=str)[: self._settings.tool_result_max_chars]}\n\n"
                    "Escreva a resposta final seguindo o JSON solicitado."
                ),
            }
        )
        return messages


class _ApproxCounter:
    def count(self, text: str) -> int:
        return max(1, len(text) // 4)


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
