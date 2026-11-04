from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from app.modules.documents.domain.document_status import (
    DocumentStatus,
)


@dataclass(frozen=True, slots=True)
class Document:
    document_id: int | None
    public_id: UUID
    name: str
    source_filename: str
    source_content_type: str
    source_size_bytes: int
    source_checksum: str
    storage_key: str
    status: DocumentStatus = DocumentStatus.PENDING
    processing_stage: str | None = None
    is_enabled: bool = True
    deleted_at: datetime | None = None
    total_pages: int | None = None
    section_count: int = 0
    chunk_count: int = 0
    parser_version: str | None = None
    chunking_version: str | None = None
    summary_version: str | None = None
    embedding_model: str | None = None
    embedding_dimensions: int | None = None
    attempt_count: int = 0
    last_error_code: str | None = None
    last_error_at: datetime | None = None
    processed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def is_retrievable(self) -> bool:
        return (
            self.status is DocumentStatus.COMPLETED
            and self.is_enabled
            and self.deleted_at is None
        )
