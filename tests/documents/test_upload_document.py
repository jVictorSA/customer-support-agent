from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from app.modules.documents.application.exceptions import (
    DocumentChecksumConflictError,
    DocumentPayloadTooLargeError,
    DocumentQueueUnavailableError,
)
from app.modules.documents.domain.settings import (
    DocumentIngestionSettings,
)
from app.modules.documents.domain.upload import PreparedUpload
from app.modules.documents.application.upload_document import (
    UploadDocumentUseCase,
)
from app.modules.documents.domain.document import Document


def build_document() -> Document:
    now = datetime(2026, 11, 4, tzinfo=UTC)
    return Document(
        document_id=1,
        public_id=uuid4(),
        name="Políticas",
        source_filename="politicas.pdf",
        source_content_type="application/pdf",
        source_size_bytes=10,
        source_checksum="a" * 64,
        storage_key="sources/" + "a" * 64 + ".pdf",
        created_at=now,
        updated_at=now,
    )


class FakeRepository:
    def __init__(self, existing: Document | None = None) -> None:
        self.existing = existing
        self.created: Document | None = None
        self.failed = False

    async def get_by_checksum(self, checksum):
        return self.existing

    async def create(self, document):
        self.created = document
        return document

    async def mark_failed(self, **kwargs):
        self.failed = True


class FakeStorage:
    async def put_pdf(self, **kwargs):
        return "sources/" + kwargs["checksum"] + ".pdf"


class FakeQueue:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    async def enqueue_ingestion(self, document_id):
        if self.fail:
            raise RuntimeError("broker down")


def settings(max_upload_bytes: int = 1024) -> DocumentIngestionSettings:
    return DocumentIngestionSettings(
        max_upload_bytes=max_upload_bytes,
        max_pages=500,
        chunk_target_tokens=800,
        chunk_max_tokens=1000,
        chunk_min_tokens=150,
        chunk_overlap_tokens=60,
        parser_version="test",
        chunking_version="test",
        summary_version="test",
    )


def upload(size: int = 10) -> PreparedUpload:
    return PreparedUpload(
        original_filename="politicas.pdf",
        content_type="application/pdf",
        size_bytes=size,
        checksum="a" * 64,
        page_count=1,
        temp_path=Path("/tmp/politicas.pdf"),
    )


async def test_upload_creates_pending_document() -> None:
    repository = FakeRepository()
    use_case = UploadDocumentUseCase(
        repository, FakeStorage(), FakeQueue(), settings()
    )

    created = await use_case.execute(upload(), name="Políticas")

    assert created.status.value == "pending"
    assert repository.created is not None
    assert created.public_id == repository.created.public_id


async def test_upload_rejects_duplicate_and_oversized() -> None:
    use_case = UploadDocumentUseCase(
        FakeRepository(build_document()),
        FakeStorage(),
        FakeQueue(),
        settings(),
    )
    with pytest.raises(DocumentChecksumConflictError):
        await use_case.execute(upload())

    big = UploadDocumentUseCase(
        FakeRepository(), FakeStorage(), FakeQueue(), settings(5)
    )
    with pytest.raises(DocumentPayloadTooLargeError):
        await big.execute(upload(size=10))


async def test_queue_failure_marks_document_failed() -> None:
    repository = FakeRepository()
    use_case = UploadDocumentUseCase(
        repository, FakeStorage(), FakeQueue(fail=True), settings()
    )

    with pytest.raises(DocumentQueueUnavailableError):
        await use_case.execute(upload())

    assert repository.failed is True
