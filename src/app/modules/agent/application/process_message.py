import logging
from typing import Any

from app.modules.agent.application.agents import (
    IntentAgent,
    QueryRewriter,
    ResponseWriter,
)
from app.modules.agent.application.grounding import GroundingValidator
from app.modules.agent.application.interfaces import (
    AgentContextPort,
    CatalogGateway,
    ChatModel,
    ComplaintGateway,
    KnowledgeRetriever,
    OrderGateway,
    TokenCounter,
)
from app.modules.agent.application.orchestrator import ReActOrchestrator
from app.modules.agent.application.prompts import (
    FALLBACK_MESSAGE,
    OUT_OF_SCOPE_MESSAGE,
    UNSAFE_REQUEST_MESSAGE,
)
from app.modules.agent.application.tools import StoreToolExecutor
from app.modules.agent.application.trace import TraceRepository
from app.modules.agent.application.trace_recorder import AgentTraceRecorder
from app.modules.agent.domain.intent import IntentKind
from app.modules.agent.domain.results import (
    OrchestratorOutcome,
    WriterAnswer,
)
from app.modules.agent.domain.settings import AgentRuntimeSettings

logger = logging.getLogger(__name__)


class ProcessMessageUseCase:
    def __init__(
        self,
        *,
        context_port: AgentContextPort,
        chat: ChatModel,
        counter: TokenCounter,
        retriever: KnowledgeRetriever,
        catalog: CatalogGateway,
        orders: OrderGateway,
        complaints: ComplaintGateway,
        traces: TraceRepository,
        settings: AgentRuntimeSettings,
    ) -> None:
        self._context_port = context_port
        self._chat = chat
        self._counter = counter
        self._retriever = retriever
        self._catalog = catalog
        self._orders = orders
        self._complaints = complaints
        self._traces = traces
        self._settings = settings
        self._grounding = GroundingValidator()

    async def execute(self, message_id: int) -> None:
        context = await self._context_port.claim(message_id)
        if context is None:
            logger.info("Message %s was already claimed or is not queued", message_id)
            return

        run_id = await self._traces.start_run(
            conversation_id=context.conversation_id,
            customer_id=context.customer_id,
            user_message_id=context.user_message_id,
            intent=None,
            prompt_version=self._settings.prompt_version,
            model=self._settings.orchestrator_model,
        )
        trace = AgentTraceRecorder(self._traces, run_id)
        fallback_used = False

        try:
            history = await self._context_port.history(
                context.conversation_id,
                limit=self._settings.history_max_messages,
            )
            intent_agent = IntentAgent(
                chat=self._chat,
                settings=self._settings,
                counter=self._counter,
                trace=trace,
            )
            rewriter = QueryRewriter(
                chat=self._chat, settings=self._settings, trace=trace
            )
            writer = ResponseWriter(
                chat=self._chat, settings=self._settings, trace=trace
            )
            tool_executor = StoreToolExecutor(
                rewriter=rewriter,
                retriever=self._retriever,
                catalog=self._catalog,
                orders=self._orders,
                complaints=self._complaints,
                trace=trace,
                settings=self._settings,
            )
            orchestrator = ReActOrchestrator(
                chat=self._chat,
                tools=tool_executor,
                settings=self._settings,
                trace=trace,
            )

            intent = await intent_agent.identify(context, history)
            await self._traces.set_run_intent(
                run_id, intent.primary_intent.value
            )

            if intent.out_of_scope_type == "harmful_or_illegal":
                outcome = OrchestratorOutcome(
                    note=(
                        "Pedido perigoso ou ilegal recusado por segurança; "
                        "nenhuma ferramenta deve ser usada."
                    )
                )
                answer = WriterAnswer(
                    message=UNSAFE_REQUEST_MESSAGE,
                    confidence="high",
                )
                await trace.validation_step(
                    output={
                        "ok": True,
                        "safety_short_circuit": "harmful_or_illegal",
                    }
                )
            else:
                if (
                    intent.out_of_scope
                    and intent.primary_intent is IntentKind.OUT_OF_SCOPE
                ):
                    outcome = OrchestratorOutcome(
                        note=(
                            "Assunto fora do escopo da loja; redirecionar sem "
                            "usar ferramentas."
                        )
                    )
                else:
                    outcome = await orchestrator.run(
                        context=context, intent=intent, history=history
                    )

                answer = await writer.write(
                    context=context,
                    intent=intent,
                    outcome=outcome,
                    history=history,
                )

                errors = self._grounding.validate(
                    intent=intent, outcome=outcome, answer=answer
                )
                if errors:
                    await trace.validation_step(
                        output={"ok": False, "errors": errors},
                        error_code="grounding_failed",
                    )
                    try:
                        answer = await writer.repair(
                            context=context,
                            intent=intent,
                            outcome=outcome,
                            history=history,
                            previous=answer,
                            errors=errors,
                        )
                    except Exception:
                        logger.exception("Writer repair failed")
                        answer = (
                            _out_of_scope_answer()
                            if intent.out_of_scope
                            else _fallback_answer()
                        )
                        fallback_used = True
                    else:
                        errors = self._grounding.validate(
                            intent=intent, outcome=outcome, answer=answer
                        )
                        if errors:
                            answer = (
                                _out_of_scope_answer()
                                if intent.out_of_scope
                                else _fallback_answer()
                            )
                            fallback_used = True
                else:
                    await trace.validation_step(output={"ok": True})

            metadata = _metadata(intent, answer, fallback_used)
            appended = await self._context_port.complete_turn(
                user_message_id=context.user_message_id,
                content=answer.message,
                metadata=metadata,
                deliver_via_webhook=context.webhook_url is not None,
                is_fallback=fallback_used,
            )
            if context.webhook_url is not None:
                try:
                    await self._context_port.enqueue_webhook(
                        appended.message_id
                    )
                except Exception:
                    logger.exception(
                        "Could not enqueue webhook delivery for message %s",
                        appended.message_id,
                    )

            await self._traces.finish_run(
                run_id,
                status="completed",
                input_tokens=trace.input_tokens,
                output_tokens=trace.output_tokens,
                fallback_used=fallback_used,
                error_code=None,
                assistant_message_id=appended.message_id,
            )
        except Exception as exc:
            await self._traces.finish_run(
                run_id,
                status="failed",
                input_tokens=trace.input_tokens,
                output_tokens=trace.output_tokens,
                fallback_used=fallback_used,
                error_code=type(exc).__name__,
            )
            raise


def _fallback_answer() -> WriterAnswer:
    return WriterAnswer(
        message=FALLBACK_MESSAGE,
        confidence="low",
        needs_human_handoff=False,
    )


def _out_of_scope_answer() -> WriterAnswer:
    return WriterAnswer(
        message=OUT_OF_SCOPE_MESSAGE,
        confidence="high",
        needs_human_handoff=False,
    )


def _metadata(
    intent, answer: WriterAnswer, fallback_used: bool
) -> dict[str, Any]:
    return {
        "intent": intent.primary_intent.value,
        "citations": [
            {
                "source_type": citation.source_type,
                "reference": citation.reference,
            }
            for citation in answer.citations
        ],
        "confidence": answer.confidence,
        "needs_human_handoff": answer.needs_human_handoff,
        "follow_up_question": answer.follow_up_question,
        "is_fallback": fallback_used,
    }
