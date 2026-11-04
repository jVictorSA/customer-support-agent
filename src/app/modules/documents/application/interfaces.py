from dataclasses import dataclass
from pathlib import Path
from typing import List, Protocol
from uuid import UUID

from app.modules.documents.domain.chunk import ChunkDraft
from app.modules.documents.domain.document import Document
from app.modules.documents.domain.document_status import (
    DocumentStatus,
    ProcessingStage,
)
from app.modules.documents.domain.parsed_document import ParsedDocument
from app.modules.documents.domain.section import (
    DocumentSection,
    SectionNode,
)


@dataclass(frozen=True, slots=True)
class PreparedUpload:
    """A PDF already streamed to disk and inspected by the presentation layer."""

    original_filename: str
    content_type: str
    size_bytes: int
    checksum: str
    page_count: int
    temp_path: Path


class DocumentRepository(Protocol):
    async def create(self, document: Document) -> Document: ...

    async def get_by_id(self, document_id: int) -> Document | None: ...

    async def get_by_public_id(
        self, public_id: UUID, *, include_deleted: bool = False
    ) -> Document | None: ...

    async def get_by_checksum(self, checksum: str) -> Document | None: ...

    async def list(
        self,
        *,
        offset: int,
        limit: int,
        status: DocumentStatus | None = None,
        is_enabled: bool | None = None,
        include_deleted: bool = False,
    ) -> tuple[List[Document], int]: ...

    async def update(self, document: Document) -> Document: ...

    async def mark_processing(
        self, document_id: int, stage: ProcessingStage
    ) -> None: ...

    async def mark_failed(
        self,
        document_id: int,
        *,
        error_code: str,
        preserve_previous_status: bool,
    ) -> None: ...

    async def replace_content(
        self,
        *,
        document_id: int,
        root: SectionNode,
        chunks: dict[UUID, List[ChunkDraft]],
        total_pages: int,
        parser_version: str,
        chunking_version: str,
        summary_version: str,
        embedding_model: str,
        embedding_dimensions: int,
    ) -> None: ...

    async def list_sections(
        self,
        document_id: int,
        *,
        offset: int,
        limit: int,
    ) -> tuple[List[DocumentSection], int]: ...

    async def list_chunks(
        self,
        document_id: int,
        *,
        offset: int,
        limit: int,
        section_public_id: UUID | None = None,
    ) -> tuple[List["ChunkRecord"], int]: ...


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


class DocumentStorage(Protocol):
    async def put_pdf(
        self, *, checksum: str, path: Path, content_type: str
    ) -> str: ...

    async def download_pdf(self, *, checksum: str, destination: Path) -> None: ...

    async def put_checkpoint(self, *, key: str, data: bytes) -> None: ...

    async def get_checkpoint(self, *, key: str) -> bytes | None: ...

    async def list_checkpoints(self, *, prefix: str) -> List[str]: ...


class DocumentParser(Protocol):
    async def parse(
        self, *, path: Path, title: str, ocr_enabled: bool
    ) -> ParsedDocument: ...


class SectionSummarizer(Protocol):
    @property
    def version(self) -> str: ...

    async def summarize(
        self,
        *,
        document_title: str,
        section_path: str,
        direct_content: str,
        child_summaries: list[tuple[str, str]],
    ) -> str: ...


class EmbeddingProvider(Protocol):
    @property
    def model(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    async def embed_passages(self, texts: list[str]) -> list[list[float]]: ...


class TaskQueue(Protocol):
    async def enqueue_ingestion(self, document_id: int) -> None: ...


class PdfInspector(Protocol):
    def inspect(self, path: Path) -> int:
        """Validate the PDF and return its page count."""
