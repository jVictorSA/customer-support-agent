from typing import Any
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


class UpdateDocumentUseCase:
    def __init__(self, repository: DocumentRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        public_id: UUID,
        *,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
        is_enabled: bool | None = None,
    ) -> Document:
        document = await self._repository.get_by_public_id(public_id)
        if document is None:
            raise DocumentNotFoundError(public_id)
        if document.status is DocumentStatus.PROCESSING and is_enabled is False:
            raise DocumentProcessingConflictError()

        updated = Document(
            document_id=document.document_id,
            public_id=document.public_id,
            name=name.strip() if name is not None else document.name,
            source_filename=document.source_filename,
            source_content_type=document.source_content_type,
            source_size_bytes=document.source_size_bytes,
            source_checksum=document.source_checksum,
            storage_key=document.storage_key,
            status=document.status,
            processing_stage=document.processing_stage,
            is_enabled=(
                is_enabled if is_enabled is not None else document.is_enabled
            ),
            deleted_at=document.deleted_at,
            total_pages=document.total_pages,
            section_count=document.section_count,
            chunk_count=document.chunk_count,
            parser_version=document.parser_version,
            chunking_version=document.chunking_version,
            summary_version=document.summary_version,
            embedding_model=document.embedding_model,
            embedding_dimensions=document.embedding_dimensions,
            attempt_count=document.attempt_count,
            last_error_code=document.last_error_code,
            last_error_at=document.last_error_at,
            processed_at=document.processed_at,
            metadata=metadata if metadata is not None else document.metadata,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )
        return await self._repository.update(updated)
