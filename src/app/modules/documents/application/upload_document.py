import logging
from pathlib import PurePath
from uuid import uuid4

from app.modules.documents.application.exceptions import (
    DocumentChecksumConflictError,
    DocumentPayloadTooLargeError,
    DocumentQueueUnavailableError,
    DocumentStorageUnavailableError,
    DocumentUnprocessableError,
    DocumentUnsupportedMediaTypeError,
)
from app.modules.documents.application.interfaces import (
    DocumentRepository,
    DocumentStorage,
    TaskQueue,
)
from app.modules.documents.domain.document import Document
from app.modules.documents.domain.document_status import (
    DocumentStatus,
    ProcessingStage,
)
from app.modules.documents.domain.settings import DocumentIngestionSettings
from app.modules.documents.domain.upload import PreparedUpload

logger = logging.getLogger(__name__)


class UploadDocumentUseCase:
    def __init__(
        self,
        repository: DocumentRepository,
        storage: DocumentStorage,
        queue: TaskQueue,
        settings: DocumentIngestionSettings,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._queue = queue
        self._settings = settings

    async def execute(
        self, upload: PreparedUpload, *, name: str | None = None
    ) -> Document:
        if upload.content_type != "application/pdf":
            raise DocumentUnsupportedMediaTypeError()
        if upload.size_bytes > self._settings.max_upload_bytes:
            raise DocumentPayloadTooLargeError()
        if upload.page_count <= 0:
            raise DocumentUnprocessableError("Document has no pages")
        if upload.page_count > self._settings.max_pages:
            raise DocumentUnprocessableError(
                f"Document has {upload.page_count} pages; the limit is "
                f"{self._settings.max_pages}"
            )

        existing = await self._repository.get_by_checksum(upload.checksum)
        if existing is not None:
            raise DocumentChecksumConflictError(existing.public_id)

        try:
            storage_key = await self._storage.put_pdf(
                checksum=upload.checksum,
                path=upload.temp_path,
                content_type=upload.content_type,
            )
        except Exception as exc:
            logger.exception("Failed to upload document to storage")
            raise DocumentStorageUnavailableError() from exc

        document = Document(
            document_id=None,
            public_id=uuid4(),
            name=(name or PurePath(upload.original_filename).stem).strip()
            or "document",
            source_filename=upload.original_filename,
            source_content_type=upload.content_type,
            source_size_bytes=upload.size_bytes,
            source_checksum=upload.checksum,
            storage_key=storage_key,
            total_pages=upload.page_count,
            status=DocumentStatus.PENDING,
            processing_stage=ProcessingStage.QUEUED.value,
        )
        try:
            created = await self._repository.create(document)
        except DocumentChecksumConflictError:
            raise
        except Exception:
            logger.exception("Failed to persist uploaded document")
            raise

        try:
            await self._queue.enqueue_ingestion(created.document_id or 0)
        except Exception as exc:
            logger.exception(
                "Failed to enqueue document %s", created.public_id
            )
            await self._repository.mark_failed(
                document_id=created.document_id or 0,
                error_code="queue_unavailable",
                preserve_previous_status=False,
            )
            raise DocumentQueueUnavailableError() from exc
        return created
