from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session
from app.modules.documents.application.delete_document import (
    DeleteDocumentUseCase,
    RestoreDocumentUseCase,
)
from app.modules.documents.application.get_document import (
    GetDocumentUseCase,
)
from app.modules.documents.application.interfaces import (
    DocumentRepository,
    DocumentStorage,
    PdfInspector,
    TaskQueue,
)
from app.modules.documents.application.list_chunks import (
    ListDocumentChunksUseCase,
)
from app.modules.documents.application.list_documents import (
    ListDocumentsUseCase,
)
from app.modules.documents.application.list_sections import (
    ListDocumentSectionsUseCase,
)
from app.modules.documents.application.reprocess_document import (
    ReprocessDocumentUseCase,
)
from app.modules.documents.domain.settings import (
    DocumentIngestionSettings,
)
from app.modules.documents.application.update_document import (
    UpdateDocumentUseCase,
)
from app.modules.documents.application.upload_document import (
    UploadDocumentUseCase,
)
from app.modules.documents.infrastructure.pdf_inspector import (
    PypdfInspector,
)
from app.modules.documents.infrastructure.queue.celery_queue import (
    CeleryTaskQueue,
)
from app.modules.documents.infrastructure.repository import (
    SqlAlchemyDocumentRepository,
)
from app.modules.documents.infrastructure.storage.minio_storage import (
    MinioDocumentStorage,
)


def get_document_repository(
    session: AsyncSession = Depends(get_session),
) -> DocumentRepository:
    return SqlAlchemyDocumentRepository(session)


def get_document_storage() -> DocumentStorage:
    settings = get_settings()
    return MinioDocumentStorage(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key.get_secret_value(),
        bucket=settings.documents_storage_bucket,
        secure=settings.minio_secure,
    )


def get_task_queue() -> TaskQueue:
    return CeleryTaskQueue()


def get_pdf_inspector() -> PdfInspector:
    return PypdfInspector()


def get_ingestion_settings() -> DocumentIngestionSettings:
    settings = get_settings()
    return DocumentIngestionSettings(
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


def get_upload_document_use_case(
    repository: DocumentRepository = Depends(get_document_repository),
    storage: DocumentStorage = Depends(get_document_storage),
    queue: TaskQueue = Depends(get_task_queue),
    settings: DocumentIngestionSettings = Depends(get_ingestion_settings),
) -> UploadDocumentUseCase:
    return UploadDocumentUseCase(repository, storage, queue, settings)


def get_list_documents_use_case(
    repository: DocumentRepository = Depends(get_document_repository),
) -> ListDocumentsUseCase:
    return ListDocumentsUseCase(repository)


def get_get_document_use_case(
    repository: DocumentRepository = Depends(get_document_repository),
) -> GetDocumentUseCase:
    return GetDocumentUseCase(repository)


def get_list_sections_use_case(
    repository: DocumentRepository = Depends(get_document_repository),
) -> ListDocumentSectionsUseCase:
    return ListDocumentSectionsUseCase(repository)


def get_list_chunks_use_case(
    repository: DocumentRepository = Depends(get_document_repository),
) -> ListDocumentChunksUseCase:
    return ListDocumentChunksUseCase(repository)


def get_update_document_use_case(
    repository: DocumentRepository = Depends(get_document_repository),
) -> UpdateDocumentUseCase:
    return UpdateDocumentUseCase(repository)


def get_delete_document_use_case(
    repository: DocumentRepository = Depends(get_document_repository),
) -> DeleteDocumentUseCase:
    return DeleteDocumentUseCase(repository)


def get_restore_document_use_case(
    repository: DocumentRepository = Depends(get_document_repository),
) -> RestoreDocumentUseCase:
    return RestoreDocumentUseCase(repository)


def get_reprocess_document_use_case(
    repository: DocumentRepository = Depends(get_document_repository),
    queue: TaskQueue = Depends(get_task_queue),
) -> ReprocessDocumentUseCase:
    return ReprocessDocumentUseCase(repository, queue)
