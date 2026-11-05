from dataclasses import replace
from uuid import UUID

from app.modules.documents.application.exceptions import (
    DocumentNotFoundError,
    DocumentProcessingConflictError,
    DocumentQueueUnavailableError,
)
from app.modules.documents.application.interfaces import (
    DocumentRepository,
    TaskQueue,
)
from app.modules.documents.domain.document import Document
from app.modules.documents.domain.document_status import (
    DocumentStatus,
    ProcessingStage,
)


class ReprocessDocumentUseCase:
    def __init__(
        self, repository: DocumentRepository, queue: TaskQueue
    ) -> None:
        self._repository = repository
        self._queue = queue

    async def execute(self, public_id: UUID) -> Document:
        document = await self._repository.get_by_public_id(public_id)
        if document is None:
            raise DocumentNotFoundError(public_id)
        if document.status in {
            DocumentStatus.PENDING,
            DocumentStatus.PROCESSING,
        }:
            raise DocumentProcessingConflictError()

        queued = await self._repository.update(
            replace(
                document,
                status=DocumentStatus.PENDING,
                processing_stage=ProcessingStage.QUEUED.value,
            )
        )
        try:
            await self._queue.enqueue_ingestion(document.document_id or 0)
        except Exception as exc:
            await self._repository.mark_failed(
                document_id=document.document_id or 0,
                error_code="queue_unavailable",
                preserve_previous_status=document.status
                is DocumentStatus.COMPLETED,
            )
            raise DocumentQueueUnavailableError() from exc
        return queued
