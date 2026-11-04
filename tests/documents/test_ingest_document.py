from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from app.modules.documents.application.exceptions import (
    DocumentIngestionError,
)
from app.modules.documents.application.ingest_document import (
    IngestDocumentUseCase,
)
from app.modules.documents.application.settings import (
    DocumentIngestionSettings,
)
from app.modules.documents.domain.content_block import (
    BlockType,
    ContentBlock,
)
from app.modules.documents.domain.document import Document
from app.modules.documents.domain.document_status import (
    DocumentStatus,
    ProcessingStage,
)
from app.modules.documents.domain.parsed_document import ParsedDocument


class WordCounter:
    def count(self, text: str) -> int:
        return len(text.split())


class FakeRepository:
    def __init__(self, document: Document) -> None:
        self.document = document
        self.stages: list[ProcessingStage] = []
        self.failure: dict[str, object] | None = None
        self.replacement: dict[str, object] | None = None

    async def get_by_id(self, document_id: int):
        return self.document

    async def mark_processing(self, document_id, stage):
        self.stages.append(stage)

    async def mark_failed(self, document_id, *, error_code, preserve_previous_status):
        self.failure = {
            "error_code": error_code,
            "preserve": preserve_previous_status,
        }

    async def replace_content(self, **kwargs):
        self.replacement = kwargs


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put_pdf(self, *, checksum, path, content_type):
        return f"sources/{checksum}.pdf"

    async def download_pdf(self, *, checksum, destination: Path):
        destination.write_bytes(b"%PDF-1.4")

    async def put_checkpoint(self, *, key, data):
        self.objects[key] = data

    async def get_checkpoint(self, *, key):
        return self.objects.get(key)

    async def list_checkpoints(self, *, prefix):
        return [key for key in self.objects if key.startswith(prefix)]


class FakeParser:
    def __init__(self) -> None:
        self.fail = False

    async def parse(self, *, path, title, ocr_enabled):
        if self.fail:
            raise DocumentIngestionError("parse_failed", "boom")
        return ParsedDocument(
            title=title,
            total_pages=2,
            blocks=(
                ContentBlock(
                    block_type=BlockType.HEADING,
                    text="1 Introdução",
                    page_start=1,
                    page_end=1,
                    position=0,
                    heading_level=1,
                ),
                ContentBlock(
                    block_type=BlockType.PARAGRAPH,
                    text="um dois tres quatro cinco seis sete oito",
                    page_start=1,
                    page_end=1,
                    position=1,
                ),
                ContentBlock(
                    block_type=BlockType.HEADING,
                    text="2 Política",
                    page_start=2,
                    page_end=2,
                    position=2,
                    heading_level=1,
                ),
                ContentBlock(
                    block_type=BlockType.PARAGRAPH,
                    text="nove dez onze doze treze quatorze",
                    page_start=2,
                    page_end=2,
                    position=3,
                ),
            ),
            parser_version="test",
        )


class FakeSummarizer:
    version = "summary-v1"

    async def summarize(self, **kwargs):
        return "Resumo da seção"


class FakeEmbedder:
    model = "fake-embedding"
    dimensions = 4

    async def embed_passages(self, texts):
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]


def document(status: DocumentStatus = DocumentStatus.PENDING) -> Document:
    now = datetime(2026, 11, 4, tzinfo=UTC)
    return Document(
        document_id=7,
        public_id=uuid4(),
        name="Manual",
        source_filename="manual.pdf",
        source_content_type="application/pdf",
        source_size_bytes=10,
        source_checksum="a" * 64,
        storage_key="sources/" + "a" * 64 + ".pdf",
        status=status,
        created_at=now,
        updated_at=now,
    )


def use_case(repository: FakeRepository, parser: FakeParser):
    return IngestDocumentUseCase(
        repository=repository,
        storage=FakeStorage(),
        parser=parser,
        summarizer=FakeSummarizer(),
        embedder=FakeEmbedder(),
        counter=WordCounter(),
        settings=DocumentIngestionSettings(
            max_upload_bytes=1024,
            max_pages=500,
            chunk_target_tokens=5,
            chunk_max_tokens=8,
            chunk_min_tokens=1,
            chunk_overlap_tokens=2,
            parser_version="test",
            chunking_version="test",
            summary_version="summary-v1",
        ),
        ocr_enabled=False,
        embedding_batch_size=8,
        embedding_batch_max_tokens=1000,
    )


async def test_ingestion_persists_sections_chunks_and_embeddings() -> None:
    repository = FakeRepository(document())

    await use_case(repository, FakeParser()).execute(7)

    assert repository.replacement is not None
    root = repository.replacement["root"]
    chunks = repository.replacement["chunks"]
    assert root.summary == "Resumo da seção"
    assert root.summary_embedding == [0.1, 0.2, 0.3, 0.4]
    assert root.children[0].summary is None
    assert all(
        draft.embedding == [0.1, 0.2, 0.3, 0.4]
        for drafts in chunks.values()
        for draft in drafts
    )
    assert repository.stages[-1] is ProcessingStage.PERSISTING


async def test_failed_reprocessing_preserves_previous_index() -> None:
    repository = FakeRepository(document(DocumentStatus.COMPLETED))
    parser = FakeParser()
    parser.fail = True

    with pytest.raises(DocumentIngestionError):
        await use_case(repository, parser).execute(7)

    assert repository.failure == {
        "error_code": "parse_failed",
        "preserve": True,
    }
