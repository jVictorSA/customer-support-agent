import asyncio
import hashlib
import tempfile
from pathlib import Path, PurePath
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    Response,
    UploadFile,
)

from app.modules.documents.application.exceptions import (
    DocumentPayloadTooLargeError,
    DocumentUnsupportedMediaTypeError,
)
from app.modules.documents.application.get_document import (
    GetDocumentUseCase,
)
from app.modules.documents.application.interfaces import (
    PdfInspector,
    PreparedUpload,
)
from app.modules.documents.application.list_chunks import (
    ListDocumentChunksUseCase,
)
from app.modules.documents.application.list_documents import (
    ListDocumentsUseCase,
)
from app.modules.documents.application.list_sections import (
    ListDocumentSectionsUseCase,
)
from app.modules.documents.application.reprocess_document import (
    ReprocessDocumentUseCase,
)
from app.modules.documents.application.settings import (
    DocumentIngestionSettings,
)
from app.modules.documents.application.update_document import (
    UpdateDocumentUseCase,
)
from app.modules.documents.application.upload_document import (
    UploadDocumentUseCase,
)
from app.modules.documents.application.delete_document import (
    DeleteDocumentUseCase,
    RestoreDocumentUseCase,
)
from app.modules.documents.domain.document_status import DocumentStatus
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
from app.modules.documents.presentation.schemas import (
    ChunkResponse,
    DocumentResponse,
    DocumentUpdateRequest,
    SectionResponse,
)
from app.presentation.pagination import Page, PaginationParams

router = APIRouter(prefix="/documents", tags=["Documents"])

CHUNK_SIZE = 1024 * 1024


@router.post("", response_model=DocumentResponse, status_code=202)
async def upload_document(
    response: Response,
    file: UploadFile = File(...),
    name: str | None = Form(None),
    use_case: UploadDocumentUseCase = Depends(get_upload_document_use_case),
    inspector: PdfInspector = Depends(get_pdf_inspector),
    settings: DocumentIngestionSettings = Depends(get_ingestion_settings),
) -> DocumentResponse:
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type != "application/pdf":
        raise DocumentUnsupportedMediaTypeError()

    temp_path, size, checksum = await _stream_to_temp(file, settings)
    try:
        page_count = await asyncio.to_thread(inspector.inspect, temp_path)
        document = await use_case.execute(
            PreparedUpload(
                original_filename=PurePath(
                    file.filename or "document.pdf"
                ).name,
                content_type=content_type,
                size_bytes=size,
                checksum=checksum,
                page_count=page_count,
                temp_path=temp_path,
            ),
            name=name,
        )
    finally:
        temp_path.unlink(missing_ok=True)

    response.headers["Location"] = f"/documents/{document.public_id}"
    return DocumentResponse.from_domain(document)


@router.get("", response_model=Page[DocumentResponse])
async def list_documents(
    pagination: PaginationParams = Depends(),
    status: DocumentStatus | None = Query(None),
    is_enabled: bool | None = Query(None),
    include_deleted: bool = Query(False),
    use_case: ListDocumentsUseCase = Depends(get_list_documents_use_case),
) -> Page[DocumentResponse]:
    documents, total = await use_case.execute(
        page=pagination.page,
        page_size=pagination.page_size,
        status=status,
        is_enabled=is_enabled,
        include_deleted=include_deleted,
    )
    return Page(
        items=[DocumentResponse.from_domain(item) for item in documents],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{public_id}", response_model=DocumentResponse)
async def get_document(
    public_id: UUID,
    include_deleted: bool = Query(False),
    use_case: GetDocumentUseCase = Depends(get_get_document_use_case),
) -> DocumentResponse:
    document = await use_case.execute(
        public_id, include_deleted=include_deleted
    )
    return DocumentResponse.from_domain(document)


@router.get("/{public_id}/sections", response_model=Page[SectionResponse])
async def list_sections(
    public_id: UUID,
    pagination: PaginationParams = Depends(),
    use_case: ListDocumentSectionsUseCase = Depends(
        get_list_sections_use_case
    ),
) -> Page[SectionResponse]:
    sections, total = await use_case.execute(
        public_id, page=pagination.page, page_size=pagination.page_size
    )
    return Page(
        items=[SectionResponse.from_domain(item) for item in sections],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/{public_id}/chunks", response_model=Page[ChunkResponse])
async def list_chunks(
    public_id: UUID,
    pagination: PaginationParams = Depends(),
    section_public_id: UUID | None = Query(None),
    use_case: ListDocumentChunksUseCase = Depends(get_list_chunks_use_case),
) -> Page[ChunkResponse]:
    chunks, total = await use_case.execute(
        public_id,
        page=pagination.page,
        page_size=pagination.page_size,
        section_public_id=section_public_id,
    )
    return Page(
        items=[ChunkResponse.from_record(item) for item in chunks],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.patch("/{public_id}", response_model=DocumentResponse)
async def update_document(
    public_id: UUID,
    payload: DocumentUpdateRequest,
    use_case: UpdateDocumentUseCase = Depends(get_update_document_use_case),
) -> DocumentResponse:
    document = await use_case.execute(
        public_id,
        name=payload.name,
        metadata=payload.metadata,
        is_enabled=payload.is_enabled,
    )
    return DocumentResponse.from_domain(document)


@router.delete("/{public_id}", status_code=204)
async def delete_document(
    public_id: UUID,
    use_case: DeleteDocumentUseCase = Depends(get_delete_document_use_case),
) -> Response:
    await use_case.execute(public_id)
    return Response(status_code=204)


@router.post("/{public_id}/restore", status_code=204)
async def restore_document(
    public_id: UUID,
    use_case: RestoreDocumentUseCase = Depends(
        get_restore_document_use_case
    ),
) -> Response:
    await use_case.execute(public_id)
    return Response(status_code=204)


@router.post(
    "/{public_id}/reprocess",
    response_model=DocumentResponse,
    status_code=202,
)
async def reprocess_document(
    public_id: UUID,
    response: Response,
    use_case: ReprocessDocumentUseCase = Depends(
        get_reprocess_document_use_case
    ),
) -> DocumentResponse:
    document = await use_case.execute(public_id)
    response.headers["Location"] = f"/documents/{document.public_id}"
    return DocumentResponse.from_domain(document)


async def _stream_to_temp(
    file: UploadFile, settings: DocumentIngestionSettings
) -> tuple[Path, int, str]:
    digest = hashlib.sha256()
    size = 0
    handle = tempfile.NamedTemporaryFile(
        prefix="upload-", suffix=".pdf", delete=False
    )
    path = Path(handle.name)
    try:
        while chunk := await file.read(CHUNK_SIZE):
            size += len(chunk)
            if size > settings.max_upload_bytes:
                raise DocumentPayloadTooLargeError()
            digest.update(chunk)
            handle.write(chunk)
    except Exception:
        handle.close()
        path.unlink(missing_ok=True)
        raise
    finally:
        if not handle.closed:
            handle.close()
    return path, size, digest.hexdigest()
