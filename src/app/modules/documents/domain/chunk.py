from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class ChunkRecord:
    chunk_id: int
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


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    """A chunk produced by the domain before persistence/embedding."""

    chunk_index: int
    content: str
    embedding_text: str
    token_count: int
    start_page: int
    end_page: int
    content_hash: str
    embedding_text_hash: str
    public_id: UUID = field(default_factory=uuid4)
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    chunk_id: int | None
    public_id: UUID
    document_id: int
    section_id: int
    chunk_index: int
    position: int
    content: str
    embedding_text: str
    content_hash: str
    embedding_text_hash: str
    token_count: int
    start_page: int
    end_page: int
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
