from uuid import UUID

from app.modules.documents.application.exceptions import (
    DocumentNotFoundError,
)
from app.modules.documents.application.interfaces import (
    DocumentRepository,
)
from app.modules.documents.domain.section import DocumentSection


class ListDocumentSectionsUseCase:
    def __init__(self, repository: DocumentRepository) -> None:
        self._repository = repository

    async def execute(
        self, public_id: UUID, *, page: int, page_size: int
    ) -> tuple[list[DocumentSection], int]:
        document = await self._repository.get_by_public_id(public_id)
        if document is None or document.document_id is None:
            raise DocumentNotFoundError(public_id)
        return await self._repository.list_sections(
            document.document_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
