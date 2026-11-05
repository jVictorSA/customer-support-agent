from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.documents.domain.chunk import ChunkRecord
from app.modules.documents.domain.document import Document
from app.modules.documents.domain.document_status import DocumentStatus
from app.modules.documents.domain.section import DocumentSection


class DocumentResponse(BaseModel):
    public_id: UUID
    name: str
    source_filename: str
    source_content_type: str
    source_size_bytes: int
    source_checksum: str
    status: DocumentStatus
    processing_stage: str | None
    is_enabled: bool
    deleted_at: datetime | None
    total_pages: int | None
    section_count: int
    chunk_count: int
    parser_version: str | None
    chunking_version: str | None
    summary_version: str | None
    embedding_model: str | None
    embedding_dimensions: int | None
    attempt_count: int
    last_error_code: str | None
    last_error_at: datetime | None
    processed_at: datetime | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, document: Document) -> "DocumentResponse":
        assert document.created_at is not None
        assert document.updated_at is not None
        return cls(
            public_id=document.public_id,
            name=document.name,
            source_filename=document.source_filename,
            source_content_type=document.source_content_type,
            source_size_bytes=document.source_size_bytes,
            source_checksum=document.source_checksum,
            status=document.status,
            processing_stage=document.processing_stage,
            is_enabled=document.is_enabled,
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
            metadata=document.metadata,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )


class DocumentUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    metadata: dict[str, Any] | None = None
    is_enabled: bool | None = None


class SectionResponse(BaseModel):
    public_id: UUID
    parent_public_id: UUID | None
    section_number: str | None
    title: str
    level: int
    path: str
    position: int
    summary: str | None
    token_count: int
    start_page: int
    end_page: int

    @classmethod
    def from_domain(cls, section: DocumentSection) -> "SectionResponse":
        return cls(
            public_id=section.public_id,
            parent_public_id=section.parent_public_id,
            section_number=section.section_number,
            title=section.title,
            level=section.level,
            path=section.path,
            position=section.position,
            summary=section.summary,
            token_count=section.token_count,
            start_page=section.start_page,
            end_page=section.end_page,
        )


class ChunkResponse(BaseModel):
    public_id: UUID
    section_public_id: UUID
    section_title: str
    section_path: str
    chunk_index: int
    position: int
    content: str
    token_count: int
    start_page: int
    end_page: int

    @classmethod
    def from_record(cls, chunk: ChunkRecord) -> "ChunkResponse":
        return cls(
            public_id=chunk.public_id,
            section_public_id=chunk.section_public_id,
            section_title=chunk.section_title,
            section_path=chunk.section_path,
            chunk_index=chunk.chunk_index,
            position=chunk.position,
            content=chunk.content,
            token_count=chunk.token_count,
            start_page=chunk.start_page,
            end_page=chunk.end_page,
        )
