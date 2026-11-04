from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from app.modules.documents.application.exceptions import (
    DocumentNotFoundError,
    DocumentProcessingConflictError,
)
from app.modules.documents.application.interfaces import (
    DocumentRepository,
)
from app.modules.documents.domain.document import Document
from app.modules.documents.domain.document_status import DocumentStatus


class DeleteDocumentUseCase:
    def __init__(self, repository: DocumentRepository) -> None:
        self._repository = repository

    async def execute(self, public_id: UUID) -> None:
        document = await self._repository.get_by_public_id(public_id)
        if document is None:
            raise DocumentNotFoundError(public_id)
        if document.status is DocumentStatus.PROCESSING:
            raise DocumentProcessingConflictError()
        document = _with_deleted(document)
        await self._repository.update(document)


class RestoreDocumentUseCase:
    def __init__(self, repository: DocumentRepository) -> None:
        self._repository = repository

    async def execute(self, public_id: UUID) -> Document:
        document = await self._repository.get_by_public_id(
            public_id, include_deleted=True
        )
        if document is None:
            raise DocumentNotFoundError(public_id)
        restored = replace(document, deleted_at=None, is_enabled=True)
        return await self._repository.update(restored)


def _with_deleted(document: Document) -> Document:
    return replace(
        document,
        deleted_at=datetime.now(UTC),
        is_enabled=False,
    )
