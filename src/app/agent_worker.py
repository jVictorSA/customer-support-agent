import asyncio
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from celery import Celery
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db import metadata as db_metadata  # noqa: F401
from app.modules.agent.application.deliver_webhook import (
    DeliverWebhookUseCase,
)
from app.modules.agent.application.interfaces import AgentContextPort
from app.modules.agent.application.process_message import (
    ProcessMessageUseCase,
)
from app.modules.agent.application.prompts import FALLBACK_MESSAGE
from app.modules.agent.domain.settings import AgentRuntimeSettings
from app.modules.agent.infrastructure.clock import SystemClock
from app.modules.agent.infrastructure.context import (
    MessageAgentContextAdapter,
    MessageDeliveryAdapter,
)
from app.modules.agent.infrastructure.llm.deepseek_chat import (
    DeepSeekChatClient,
)
from app.modules.agent.infrastructure.retrieval.documents_retriever import (
    DocumentsKnowledgeRetriever,
)
from app.modules.agent.infrastructure.tools.catalog import (
    SqlAlchemyCatalogGateway,
)
from app.modules.agent.infrastructure.tools.complaints import (
    ComplaintGatewayAdapter,
)
from app.modules.agent.infrastructure.tools.orders import (
    SqlAlchemyOrderGateway,
)
from app.modules.agent.infrastructure.tools.text_to_sql import (
    TextToSqlToolAdapter,
)
from app.modules.agent.infrastructure.trace.repository import (
    SqlAlchemyTraceRepository,
)
from app.modules.agent.infrastructure.token_counter import AgentTokenCounter
from app.modules.agent.infrastructure.webhook.sender import (
    HttpWebhookSender,
)
from app.modules.complaints.application.register_complaint import (
    RegisterComplaintUseCase,
)
from app.modules.complaints.infrastructure.handoff import (
    RepositoryConversationHandoff,
)
from app.modules.complaints.infrastructure.repository import (
    SqlAlchemyComplaintRepository,
)
from app.modules.conversations.infrastructure.repository import (
    SqlAlchemyConversationRepository,
)
from app.modules.customers.infrastructure.repository import (
    SqlAlchemyCustomerRepository,
)
from app.modules.documents.application.search_knowledge import (
    SearchKnowledgeUseCase,
)
from app.modules.documents.domain.retrieval import KnowledgeSearchSettings
from app.modules.documents.infrastructure.embeddings.jina_embedder import (
    JinaEmbeddingProvider,
)
from app.modules.documents.infrastructure.knowledge_search import (
    SqlAlchemyKnowledgeSearchRepository,
)
from app.modules.messages.infrastructure.queue.celery_queue import (
    CeleryConversationQueue,
)
from app.modules.messages.infrastructure.repository import (
    SqlAlchemyMessageRepository,
)
from app.modules.text_to_sql.application.answer import TextToSqlUseCase
from app.modules.text_to_sql.domain.catalog import CATALOG
from app.modules.text_to_sql.domain.settings import TextToSqlSettings
from app.modules.text_to_sql.infrastructure.sql.executor import (
    SqlAlchemyReadOnlyExecutor,
)
from app.modules.text_to_sql.infrastructure.sql.metrics import (
    SqlMetricBuilder,
)
from app.modules.text_to_sql.infrastructure.sql.validator import (
    SqlGlotValidator,
)

logger = logging.getLogger(__name__)

settings = get_settings()

celery_app = Celery(
    "customer_support_agent",
    broker=settings.rabbitmq_url,
    include=["app.agent_worker"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_ignore_result=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    task_soft_time_limit=settings.celery_agent_task_soft_time_limit,
    task_time_limit=settings.celery_agent_task_time_limit,
    task_default_queue="conversations.process",
    task_routes={
        "conversations.process": {"queue": "conversations.process"},
        "conversations.deliver_webhook": {"queue": "conversations.process"},
    },
    timezone="UTC",
    enable_utc=True,
)

__all__ = ["celery_app"]


@celery_app.task(
    bind=True,
    name="conversations.process",
    max_retries=settings.celery_agent_max_retries,
)
def process_message_task(self, message_id: int) -> None:
    try:
        asyncio.run(_process(message_id))
    except Exception as exc:
        retries = self.request.retries
        if retries >= self.max_retries:
            logger.exception(
                "Message %s failed after %s retries", message_id, retries
            )
            asyncio.run(_fallback(message_id, type(exc).__name__))
            raise
        countdown = [30, 120, 300][min(retries, 2)]
        asyncio.run(_release(message_id))
        logger.warning(
            "Retrying message %s in %ss (%s/%s)",
            message_id,
            countdown,
            retries + 1,
            self.max_retries,
        )
        raise self.retry(exc=exc, countdown=countdown) from exc


@celery_app.task(
    bind=True,
    name="conversations.deliver_webhook",
    max_retries=settings.conversation_webhook_max_retries,
)
def deliver_webhook_task(self, assistant_message_id: int) -> None:
    try:
        asyncio.run(_deliver(assistant_message_id))
    except Exception as exc:
        retries = self.request.retries
        if retries >= self.max_retries:
            logger.exception(
                "Webhook delivery failed for message %s after %s retries",
                assistant_message_id,
                retries,
            )
            raise
        countdown = [15, 60, 180, 600, 1800][min(retries, 4)]
        raise self.retry(exc=exc, countdown=countdown) from exc


@asynccontextmanager
async def _session() -> AsyncGenerator[AsyncSession, None]:
    settings = get_settings()
    engine = create_async_engine(
        settings.sqlalchemy_database_url,
        pool_pre_ping=True,
        connect_args={"timeout": settings.db_connect_timeout},
    )
    factory = async_sessionmaker(
        bind=engine, expire_on_commit=False, autoflush=False
    )
    try:
        async with factory() as session:
            yield session
    finally:
        await engine.dispose()


def _agent_settings() -> AgentRuntimeSettings:
    settings = get_settings()
    return AgentRuntimeSettings(
        max_iterations=settings.agent_max_iterations,
        history_max_messages=settings.agent_history_max_messages,
        history_max_tokens=settings.agent_history_max_tokens,
        prompt_version=settings.agent_prompt_version,
        text_to_sql_enabled=(
            settings.agent_text_to_sql_enabled
            and settings.sqlalchemy_text_to_sql_url is not None
        ),
        disable_thinking=settings.agent_disable_thinking,
        intent_model=(
            settings.agent_intent_model or settings.deepseek_agent_model
        ),
        orchestrator_model=(
            settings.agent_orchestrator_model
            or settings.deepseek_agent_model
        ),
        rewriter_model=(
            settings.agent_rewriter_model or settings.deepseek_agent_model
        ),
        writer_model=(
            settings.agent_writer_model or settings.deepseek_agent_model
        ),
        intent_temperature=settings.agent_intent_temperature,
        orchestrator_temperature=settings.agent_orchestrator_temperature,
        rewriter_temperature=settings.agent_rewriter_temperature,
        writer_temperature=settings.agent_writer_temperature,
        intent_max_tokens=settings.agent_intent_max_tokens,
        orchestrator_max_tokens=settings.agent_orchestrator_max_tokens,
        rewriter_max_tokens=settings.agent_rewriter_max_tokens,
        writer_max_tokens=settings.agent_writer_max_tokens,
        tool_result_max_chars=settings.agent_tool_result_max_chars,
        store_timezone=settings.store_timezone,
        store_holidays=tuple(
            value.strip()
            for value in settings.store_holidays.split(",")
            if value.strip()
        ),
        store_metro_cep_prefixes=tuple(
            value.strip()
            for value in settings.store_metro_cep_prefixes.split(",")
            if value.strip()
        ),
    )


def _chat() -> DeepSeekChatClient:
    settings = get_settings()
    return DeepSeekChatClient(
        api_key=(
            settings.deepseek_api_key.get_secret_value()
            if settings.deepseek_api_key
            else ""
        ),
        base_url=settings.deepseek_base_url,
        default_model=settings.deepseek_model,
        timeout=settings.deepseek_timeout,
        max_retries=settings.deepseek_max_retries,
        disable_thinking=settings.agent_disable_thinking,
    )


def _text_to_sql_settings() -> TextToSqlSettings:
    settings = get_settings()
    return TextToSqlSettings(
        model=settings.text_to_sql_model_name,
        temperature=settings.text_to_sql_temperature,
        max_tokens=settings.text_to_sql_max_tokens,
        max_attempts=settings.text_to_sql_max_attempts,
        max_rows=settings.text_to_sql_max_rows,
        writer_rows=settings.text_to_sql_writer_rows,
        statement_timeout_ms=settings.text_to_sql_statement_timeout_ms,
        max_joins=settings.text_to_sql_max_joins,
        max_ast_depth=settings.text_to_sql_max_ast_depth,
        max_ctes=settings.text_to_sql_max_ctes,
        max_union_branches=settings.text_to_sql_max_union_branches,
        max_result_chars=settings.text_to_sql_max_result_chars,
    )


def _text_to_sql_gateway(
    engine: AsyncEngine,
) -> TextToSqlToolAdapter:
    return TextToSqlToolAdapter(
        TextToSqlUseCase(
            chat=_chat(),
            validator=SqlGlotValidator(),
            executor=SqlAlchemyReadOnlyExecutor(engine),
            metrics=SqlMetricBuilder(),
            catalog=CATALOG,
            settings=_text_to_sql_settings(),
        )
    )


def _context_port(session: AsyncSession) -> MessageAgentContextAdapter:
    return MessageAgentContextAdapter(
        messages=SqlAlchemyMessageRepository(session),
        conversations=SqlAlchemyConversationRepository(session),
        customers=SqlAlchemyCustomerRepository(session),
        queue=CeleryConversationQueue(),
    )


async def _process(message_id: int) -> None:
    settings = get_settings()
    text_to_sql_engine: AsyncEngine | None = None
    text_to_sql = None
    try:
        if settings.agent_text_to_sql_enabled:
            url = settings.sqlalchemy_text_to_sql_url
            if url is None:
                logger.warning(
                    "AGENT_TEXT_TO_SQL_ENABLED is true but the read-only "
                    "Text-to-SQL database URL is not configured"
                )
            else:
                text_to_sql_engine = create_async_engine(
                    url,
                    poolclass=NullPool,
                    connect_args={"timeout": settings.db_connect_timeout},
                )
                text_to_sql = _text_to_sql_gateway(text_to_sql_engine)

        async with _session() as session:
            messages = SqlAlchemyMessageRepository(session)
            conversations = SqlAlchemyConversationRepository(session)
            customers = SqlAlchemyCustomerRepository(session)
            queue = CeleryConversationQueue()
            context = MessageAgentContextAdapter(
                messages=messages,
                conversations=conversations,
                customers=customers,
                queue=queue,
            )
            search = SearchKnowledgeUseCase(
                embedder=JinaEmbeddingProvider(
                    api_key=(
                        settings.jina_api_key.get_secret_value()
                        if settings.jina_api_key
                        else ""
                    ),
                    base_url=settings.jina_base_url,
                    model=settings.jina_embedding_model,
                    dimensions=settings.jina_embedding_dimensions,
                    timeout=settings.jina_timeout,
                    max_retries=settings.jina_max_retries,
                    rpm=settings.jina_rpm,
                    tpm=settings.jina_tpm,
                ),
                repository=SqlAlchemyKnowledgeSearchRepository(session),
                settings=KnowledgeSearchSettings(
                    vector_top_k=settings.retrieval_vector_top_k,
                    lexical_top_k=settings.retrieval_lexical_top_k,
                    rrf_k=settings.retrieval_rrf_k,
                    final_k=settings.retrieval_final_k,
                    context_max_tokens=settings.retrieval_context_max_tokens,
                ),
            )
            orders = SqlAlchemyOrderGateway(session)
            complaints = ComplaintGatewayAdapter(
                use_case=RegisterComplaintUseCase(
                    repository=SqlAlchemyComplaintRepository(session),
                    handoff=RepositoryConversationHandoff(conversations),
                ),
                orders=orders,
            )
            clock = SystemClock()
            use_case = ProcessMessageUseCase(
                context_port=context,
                chat=_chat(),
                counter=AgentTokenCounter(),
                retriever=DocumentsKnowledgeRetriever(search),
                catalog=SqlAlchemyCatalogGateway(session, clock),
                orders=orders,
                complaints=complaints,
                traces=SqlAlchemyTraceRepository(session),
                settings=_agent_settings(),
                text_to_sql=text_to_sql,
                clock=clock,
            )
            await use_case.execute(message_id)
    finally:
        if text_to_sql_engine is not None:
            await text_to_sql_engine.dispose()


async def _release(message_id: int) -> None:
    async with _session() as session:
        await SqlAlchemyMessageRepository(session).release_for_retry(
            message_id
        )


async def _fallback(message_id: int, error_code: str) -> None:
    async with _session() as session:
        messages = SqlAlchemyMessageRepository(session)
        context = MessageAgentContextAdapter(
            messages=messages,
            conversations=SqlAlchemyConversationRepository(session),
            customers=SqlAlchemyCustomerRepository(session),
            queue=CeleryConversationQueue(),
        )
        loaded = await context.load_context(message_id)
        if loaded is None:
            return
        try:
            appended = await context.complete_turn(
                user_message_id=message_id,
                content=FALLBACK_MESSAGE,
                metadata={
                    "intent": "fallback",
                    "citations": [],
                    "confidence": "low",
                    "is_fallback": True,
                },
                deliver_via_webhook=loaded.webhook_url is not None,
                is_fallback=True,
            )
            await context.fail(message_id, error_code=error_code)
            if loaded.webhook_url is not None:
                await context.enqueue_webhook(appended.message_id)
        except Exception:
            logger.exception("Could not persist fallback for %s", message_id)


async def _deliver(assistant_message_id: int) -> None:
    settings = get_settings()
    async with _session() as session:
        targets = MessageDeliveryAdapter(
            messages=SqlAlchemyMessageRepository(session),
            conversations=SqlAlchemyConversationRepository(session),
        )
        use_case = DeliverWebhookUseCase(
            targets=targets,
            sender=HttpWebhookSender(
                secret=settings.conversation_webhook_secret.get_secret_value(),
                timeout=settings.conversation_webhook_timeout,
            ),
        )
        await use_case.execute(assistant_message_id)
