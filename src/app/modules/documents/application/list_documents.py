from app.modules.documents.application.interfaces import (
    DocumentRepository,
)
from app.modules.documents.domain.document import Document
from app.modules.documents.domain.document_status import DocumentStatus


class ListDocumentsUseCase:
    def __init__(self, repository: DocumentRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        *,
        page: int,
        page_size: int,
        status: DocumentStatus | None = None,
        is_enabled: bool | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[Document], int]:
        return await self._repository.list(
            offset=(page - 1) * page_size,
            limit=page_size,
            status=status,
            is_enabled=is_enabled,
            include_deleted=include_deleted,
        )
