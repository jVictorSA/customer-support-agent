from uuid import UUID

from app.modules.documents.application.exceptions import (
    DocumentNotFoundError,
)
from app.modules.documents.application.interfaces import (
    DocumentRepository,
)
from app.modules.documents.domain.document import Document


class GetDocumentUseCase:
    def __init__(self, repository: DocumentRepository) -> None:
        self._repository = repository

    async def execute(
        self, public_id: UUID, *, include_deleted: bool = False
    ) -> Document:
        document = await self._repository.get_by_public_id(
            public_id, include_deleted=include_deleted
        )
        if document is None:
            raise DocumentNotFoundError(public_id)
        return document
