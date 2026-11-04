from uuid import UUID

from app.modules.documents.application.exceptions import (
    DocumentNotFoundError,
)
from app.modules.documents.application.interfaces import (
    ChunkRecord,
    DocumentRepository,
)


class ListDocumentChunksUseCase:
    def __init__(self, repository: DocumentRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        public_id: UUID,
        *,
        page: int,
        page_size: int,
        section_public_id: UUID | None = None,
    ) -> tuple[list[ChunkRecord], int]:
        document = await self._repository.get_by_public_id(public_id)
        if document is None or document.document_id is None:
            raise DocumentNotFoundError(public_id)
        return await self._repository.list_chunks(
            document.document_id,
            offset=(page - 1) * page_size,
            limit=page_size,
            section_public_id=section_public_id,
        )
