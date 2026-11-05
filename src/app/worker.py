import asyncio
import logging

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.modules.documents.application.ingest_document import (
    IngestDocumentUseCase,
)
from app.modules.documents.domain.settings import (
    DocumentIngestionSettings,
)
from app.modules.documents.infrastructure.embeddings.jina_embedder import (
    JinaEmbeddingProvider,
)
from app.modules.documents.infrastructure.parsing.docling_parser import (
    DoclingPdfParser,
)
from app.modules.documents.infrastructure.queue.celery_app import (
    celery_app,
)
from app.modules.documents.infrastructure.repository import (
    SqlAlchemyDocumentRepository,
)
from app.modules.documents.infrastructure.storage.minio_storage import (
    MinioDocumentStorage,
)
from app.modules.documents.infrastructure.summarization.deepseek_summarizer import (
    DeepSeekSectionSummarizer,
)
from app.modules.documents.infrastructure.token_counter import (
    TiktokenTokenCounter,
)

logger = logging.getLogger(__name__)

__all__ = ["celery_app"]


@celery_app.task(
    bind=True,
    name="documents.ingest",
    max_retries=get_settings().celery_max_retries,
)
def ingest_document_task(self, document_id: int) -> None:
    try:
        asyncio.run(_ingest(document_id))
    except Exception as exc:
        retries = self.request.retries
        if retries >= self.max_retries:
            logger.exception(
                "Document %s failed after %s retries", document_id, retries
            )
            raise
        countdown = [60, 300, 900][min(retries, 2)]
        logger.warning(
            "Retrying document %s in %ss (%s/%s)",
            document_id,
            countdown,
            retries + 1,
            self.max_retries,
        )
        raise self.retry(exc=exc, countdown=countdown) from exc


async def _ingest(document_id: int) -> None:
    settings = get_settings()
    engine = create_async_engine(
        settings.sqlalchemy_database_url,
        pool_pre_ping=True,
        connect_args={"timeout": settings.db_connect_timeout},
    )
    session_factory = async_sessionmaker(
        bind=engine, expire_on_commit=False, autoflush=False
    )
    storage = MinioDocumentStorage(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key.get_secret_value(),
        bucket=settings.documents_storage_bucket,
        secure=settings.minio_secure,
    )
    parser = DoclingPdfParser(parser_version=settings.documents_parser_version)
    summarizer = DeepSeekSectionSummarizer(
        api_key=(
            settings.deepseek_api_key.get_secret_value()
            if settings.deepseek_api_key
            else ""
        ),
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
        version=settings.documents_summary_version,
        timeout=settings.deepseek_timeout,
        max_retries=settings.deepseek_max_retries,
        max_tokens=settings.deepseek_summary_max_tokens,
        disable_thinking=settings.deepseek_disable_thinking,
    )
    embedder = JinaEmbeddingProvider(
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
    )
    ingestion_settings = DocumentIngestionSettings(
        max_upload_bytes=settings.documents_max_upload_mb * 1024 * 1024,
        max_pages=settings.documents_max_pages,
        chunk_target_tokens=settings.documents_chunk_target_tokens,
        chunk_max_tokens=settings.documents_chunk_max_tokens,
        chunk_min_tokens=settings.documents_chunk_min_tokens,
        chunk_overlap_tokens=settings.documents_chunk_overlap_tokens,
        parser_version=settings.documents_parser_version,
        chunking_version=settings.documents_chunking_version,
        summary_version=settings.documents_summary_version,
        summary_input_max_tokens=settings.deepseek_summary_input_max_tokens,
    )
    try:
        async with session_factory() as session:
            use_case = IngestDocumentUseCase(
                repository=_repository(session),
                storage=storage,
                parser=parser,
                summarizer=summarizer,
                embedder=embedder,
                counter=TiktokenTokenCounter(),
                settings=ingestion_settings,
                ocr_enabled=settings.documents_ocr_enabled,
                embedding_batch_size=settings.jina_batch_size,
                embedding_batch_max_tokens=settings.jina_batch_max_tokens,
            )
            await use_case.execute(document_id)
    finally:
        await engine.dispose()


def _repository(session: AsyncSession) -> SqlAlchemyDocumentRepository:
    return SqlAlchemyDocumentRepository(session)
