from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.modules.documents.application.exceptions import (
    DocumentChecksumConflictError,
)
from app.modules.documents.domain.chunk import ChunkRecord
from app.modules.documents.domain.settings import (
    DocumentIngestionSettings,
)
from app.modules.documents.domain.document import Document
from app.modules.documents.domain.document_status import DocumentStatus
from app.modules.documents.domain.section import DocumentSection
from app.modules.documents.presentation.dependencies import (
    get_delete_document_use_case,
    get_get_document_use_case,
    get_ingestion_settings,
    get_list_chunks_use_case,
    get_list_documents_use_case,
    get_list_sections_use_case,
    get_pdf_inspector,
    get_reprocess_document_use_case,
    get_restore_document_use_case,
    get_update_document_use_case,
    get_upload_document_use_case,
)

DOCUMENT_ID = uuid4()
SECTION_ID = uuid4()
CHUNK_ID = uuid4()
NOW = datetime(2026, 11, 4, tzinfo=UTC)
DOCUMENT = Document(
    document_id=1,
    public_id=DOCUMENT_ID,
    name="Políticas",
    source_filename="politicas.pdf",
    source_content_type="application/pdf",
    source_size_bytes=1024,
    source_checksum="a" * 64,
    storage_key="sources/" + "a" * 64 + ".pdf",
    status=DocumentStatus.COMPLETED,
    is_enabled=True,
    section_count=2,
    chunk_count=1,
    created_at=NOW,
    updated_at=NOW,
)
SECTION = DocumentSection(
    section_id=1,
    public_id=SECTION_ID,
    document_id=1,
    parent_section_id=None,
    parent_public_id=None,
    section_number="1",
    title="Introdução",
    level=1,
    path="n0.n1",
    position=1,
    content="",
    summary="Resumo",
    summary_embedding=None,
    token_count=0,
    start_page=1,
    end_page=1,
)
CHUNK = ChunkRecord(
    chunk_id=1,
    public_id=CHUNK_ID,
    section_public_id=SECTION_ID,
    section_title="Introdução",
    section_path="n0.n1",
    chunk_index=0,
    position=0,
    content="Conteúdo",
    token_count=2,
    start_page=1,
    end_page=1,
)


class FakeInspector:
    def inspect(self, path) -> int:
        return 1


class FakeUpload:
    def __init__(self) -> None:
        self.upload = None

    async def execute(self, upload, *, name=None):
        self.upload = upload
        return DOCUMENT


class FakeList:
    async def execute(self, **kwargs):
        return [DOCUMENT], 1


class FakeGet:
    async def execute(self, public_id, **kwargs):
        return DOCUMENT


class FakeSections:
    async def execute(self, public_id, **kwargs):
        return [SECTION], 1


class FakeChunks:
    async def execute(self, public_id, **kwargs):
        return [CHUNK], 1


class FakeUpdate:
    async def execute(self, public_id, **kwargs):
        return DOCUMENT


class FakeDelete:
    async def execute(self, public_id):
        return None


class FakeRestore:
    async def execute(self, public_id):
        return DOCUMENT


class FakeReprocess:
    async def execute(self, public_id):
        return DOCUMENT


def _override_dependencies() -> None:
    app.dependency_overrides[get_upload_document_use_case] = FakeUpload
    app.dependency_overrides[get_pdf_inspector] = FakeInspector
    app.dependency_overrides[get_ingestion_settings] = lambda: (
        DocumentIngestionSettings(
            max_upload_bytes=1024 * 1024,
            max_pages=500,
            chunk_target_tokens=800,
            chunk_max_tokens=1000,
            chunk_min_tokens=150,
            chunk_overlap_tokens=60,
            parser_version="test",
            chunking_version="test",
            summary_version="test",
        )
    )
    app.dependency_overrides[get_list_documents_use_case] = FakeList
    app.dependency_overrides[get_get_document_use_case] = FakeGet
    app.dependency_overrides[get_list_sections_use_case] = FakeSections
    app.dependency_overrides[get_list_chunks_use_case] = FakeChunks
    app.dependency_overrides[get_update_document_use_case] = FakeUpdate
    app.dependency_overrides[get_delete_document_use_case] = FakeDelete
    app.dependency_overrides[get_restore_document_use_case] = FakeRestore
    app.dependency_overrides[get_reprocess_document_use_case] = FakeReprocess


def test_upload_and_read_surface(client: TestClient) -> None:
    _override_dependencies()

    upload = client.post(
        "/documents",
        files={"file": ("politicas.pdf", b"%PDF-1.4\n", "application/pdf")},
        data={"name": "Políticas"},
    )
    listing = client.get("/documents?page=1&page_size=10")
    detail = client.get(f"/documents/{DOCUMENT_ID}")
    sections = client.get(f"/documents/{DOCUMENT_ID}/sections")
    chunks = client.get(f"/documents/{DOCUMENT_ID}/chunks")

    app.dependency_overrides.clear()

    assert upload.status_code == 202
    assert upload.headers["location"] == f"/documents/{DOCUMENT_ID}"
    assert upload.json()["public_id"] == str(DOCUMENT_ID)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert detail.status_code == 200
    assert sections.json()["items"][0]["path"] == "n0.n1"
    assert chunks.json()["items"][0]["content"] == "Conteúdo"
    assert "embedding" not in chunks.json()["items"][0]


def test_upload_rejects_non_pdf(client: TestClient) -> None:
    _override_dependencies()

    response = client.post(
        "/documents",
        files={"file": ("x.txt", b"hello", "text/plain")},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 415
    assert response.json()["code"] == "document_unsupported_media_type"


def test_upload_reports_checksum_conflict(client: TestClient) -> None:
    class ConflictUpload:
        async def execute(self, upload, *, name=None):
            raise DocumentChecksumConflictError(DOCUMENT_ID)

    _override_dependencies()
    app.dependency_overrides[get_upload_document_use_case] = ConflictUpload

    response = client.post(
        "/documents",
        files={"file": ("politicas.pdf", b"%PDF-1.4\n", "application/pdf")},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["code"] == "document_checksum_conflict"


def test_update_delete_restore_and_reprocess(client: TestClient) -> None:
    _override_dependencies()

    update = client.patch(
        f"/documents/{DOCUMENT_ID}", json={"name": "Novo nome"}
    )
    delete = client.delete(f"/documents/{DOCUMENT_ID}")
    restore = client.post(f"/documents/{DOCUMENT_ID}/restore")
    reprocess = client.post(f"/documents/{DOCUMENT_ID}/reprocess")

    app.dependency_overrides.clear()

    assert update.status_code == 200
    assert delete.status_code == 204
    assert restore.status_code == 204
    assert reprocess.status_code == 202
