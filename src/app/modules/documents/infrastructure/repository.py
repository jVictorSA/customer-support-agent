from datetime import UTC, datetime
from typing import List
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.application.exceptions import (
    DocumentChecksumConflictError,
)
from app.modules.documents.domain.chunk import ChunkRecord
from app.modules.documents.domain.chunk import ChunkDraft
from app.modules.documents.domain.document import Document
from app.modules.documents.domain.document_status import (
    DocumentStatus,
    ProcessingStage,
)
from app.modules.documents.domain.section import (
    DocumentSection,
    SectionNode,
)
from app.modules.documents.infrastructure.models import (
    DocumentChunkModel,
    DocumentModel,
    DocumentSectionModel,
)


class SqlAlchemyDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, document: Document) -> Document:
        async with self._session.begin():
            model = DocumentModel(
                public_id=document.public_id,
                name=document.name,
                source_filename=document.source_filename,
                source_content_type=document.source_content_type,
                source_size_bytes=document.source_size_bytes,
                source_checksum=document.source_checksum,
                storage_key=document.storage_key,
                status=document.status,
                processing_stage=document.processing_stage,
                total_pages=document.total_pages,
                is_enabled=document.is_enabled,
                metadata_=document.metadata,
            )
            try:
                async with self._session.begin_nested():
                    self._session.add(model)
                    await self._session.flush()
            except IntegrityError as exc:
                existing = await self._session.scalar(
                    select(DocumentModel).where(
                        DocumentModel.source_checksum
                        == document.source_checksum
                    )
                )
                if existing is not None:
                    raise DocumentChecksumConflictError(
                        existing.public_id
                    ) from exc
                raise
            return model.to_domain()

    async def get_by_id(self, document_id: int) -> Document | None:
        async with self._session.begin():
            model = await self._session.get(DocumentModel, document_id)
            return model.to_domain() if model is not None else None

    async def get_by_public_id(
        self, public_id: UUID, *, include_deleted: bool = False
    ) -> Document | None:
        async with self._session.begin():
            filters = [DocumentModel.public_id == public_id]
            if not include_deleted:
                filters.append(DocumentModel.deleted_at.is_(None))
            model = await self._session.scalar(
                select(DocumentModel).where(*filters)
            )
            return model.to_domain() if model is not None else None

    async def get_by_checksum(self, checksum: str) -> Document | None:
        async with self._session.begin():
            model = await self._session.scalar(
                select(DocumentModel).where(
                    DocumentModel.source_checksum == checksum
                )
            )
            return model.to_domain() if model is not None else None

    async def list(
        self,
        *,
        offset: int,
        limit: int,
        status: DocumentStatus | None = None,
        is_enabled: bool | None = None,
        include_deleted: bool = False,
    ) -> tuple[List[Document], int]:
        async with self._session.begin():
            filters = []
            if status is not None:
                filters.append(DocumentModel.status == status)
            if is_enabled is not None:
                filters.append(DocumentModel.is_enabled == is_enabled)
            if not include_deleted:
                filters.append(DocumentModel.deleted_at.is_(None))

            total = await self._session.scalar(
                select(func.count())
                .select_from(DocumentModel)
                .where(*filters)
            )
            models = await self._session.scalars(
                select(DocumentModel)
                .where(*filters)
                .order_by(
                    DocumentModel.created_at.desc(),
                    DocumentModel.document_id.desc(),
                )
                .offset(offset)
                .limit(limit)
            )
            return [model.to_domain() for model in models], int(total or 0)

    async def update(self, document: Document) -> Document:
        async with self._session.begin():
            model = await self._session.get(
                DocumentModel, document.document_id
            )
            if model is None:
                raise ValueError("Document does not exist")
            model.name = document.name
            model.metadata_ = document.metadata
            model.is_enabled = document.is_enabled
            model.deleted_at = document.deleted_at
            model.status = document.status
            model.processing_stage = document.processing_stage
            model.attempt_count = document.attempt_count
            model.last_error_code = document.last_error_code
            model.last_error_at = document.last_error_at
            await self._session.flush()
            return model.to_domain()

    async def mark_processing(
        self, document_id: int, stage: ProcessingStage
    ) -> None:
        async with self._session.begin():
            model = await self._session.get(DocumentModel, document_id)
            if model is None:
                return
            if model.status is not DocumentStatus.PROCESSING:
                model.attempt_count = model.attempt_count + 1
            model.status = DocumentStatus.PROCESSING
            model.processing_stage = stage.value
            model.last_error_code = None
            model.last_error_at = None
            await self._session.flush()

    async def mark_failed(
        self,
        document_id: int,
        *,
        error_code: str,
        preserve_previous_status: bool,
    ) -> None:
        async with self._session.begin():
            model = await self._session.get(DocumentModel, document_id)
            if model is None:
                return
            model.status = (
                DocumentStatus.COMPLETED
                if preserve_previous_status
                else DocumentStatus.FAILED
            )
            model.processing_stage = None
            model.last_error_code = error_code
            model.last_error_at = datetime.now(UTC)
            await self._session.flush()

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
    ) -> None:
        async with self._session.begin():
            model = await self._session.get(DocumentModel, document_id)
            if model is None:
                raise ValueError("Document does not exist")
            if model.deleted_at is not None:
                # A concurrent soft-delete wins; do not resurrect content.
                return

            await self._session.execute(
                delete(DocumentChunkModel).where(
                    DocumentChunkModel.document_id == document_id
                )
            )
            await self._session.execute(
                delete(DocumentSectionModel).where(
                    DocumentSectionModel.document_id == document_id
                )
            )

            section_ids: dict[UUID, int] = {}

            async def insert_node(
                node: SectionNode, parent_id: int | None
            ) -> None:
                section = DocumentSectionModel(
                    public_id=node.public_id,
                    document_id=document_id,
                    parent_section_id=parent_id,
                    section_number=node.number,
                    title=node.title,
                    level=node.level,
                    path=node.path,
                    position=node.position,
                    content=node.content,
                    summary=node.summary,
                    summary_embedding=node.summary_embedding,
                    token_count=node.token_count,
                    start_page=node.start_page,
                    end_page=node.end_page,
                )
                self._session.add(section)
                await self._session.flush()
                section_ids[node.public_id] = section.section_id
                for child in node.children:
                    await insert_node(child, section.section_id)

            await insert_node(root, None)

            position = 0
            for section_public_id, drafts in chunks.items():
                for draft in drafts:
                    self._session.add(
                        DocumentChunkModel(
                            public_id=draft.public_id,
                            document_id=document_id,
                            section_id=section_ids[section_public_id],
                            chunk_index=draft.chunk_index,
                            position=position,
                            content=draft.content,
                            embedding_text=draft.embedding_text,
                            content_hash=draft.content_hash,
                            embedding_text_hash=draft.embedding_text_hash,
                            embedding=draft.embedding,
                            token_count=draft.token_count,
                            start_page=draft.start_page,
                            end_page=draft.end_page,
                        )
                    )
                    position += 1

            model.status = DocumentStatus.COMPLETED
            model.processing_stage = None
            model.total_pages = total_pages
            model.section_count = len(
                [node for node in _walk(root) if node.level > 0]
            ) + 1
            model.chunk_count = position
            model.parser_version = parser_version
            model.chunking_version = chunking_version
            model.summary_version = summary_version
            model.embedding_model = embedding_model
            model.embedding_dimensions = embedding_dimensions
            model.processed_at = datetime.now(UTC)
            model.last_error_code = None
            model.last_error_at = None
            await self._session.flush()

    async def list_sections(
        self, document_id: int, *, offset: int, limit: int
    ) -> tuple[List[DocumentSection], int]:
        async with self._session.begin():
            total = await self._session.scalar(
                select(func.count())
                .select_from(DocumentSectionModel)
                .where(DocumentSectionModel.document_id == document_id)
            )
            models = (
                await self._session.scalars(
                    select(DocumentSectionModel)
                    .where(DocumentSectionModel.document_id == document_id)
                    .order_by(DocumentSectionModel.position)
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
            all_ids = (
                await self._session.execute(
                    select(
                        DocumentSectionModel.section_id,
                        DocumentSectionModel.public_id,
                        DocumentSectionModel.parent_section_id,
                    ).where(
                        DocumentSectionModel.document_id == document_id
                    )
                )
            ).all()
            public_ids = {
                section_id: public_id
                for section_id, public_id, _ in all_ids
            }
            parent_public = {
                public_id: public_ids.get(parent_section_id)
                for _, public_id, parent_section_id in all_ids
            }
            return [
                model.to_domain(parent_public.get(model.public_id))
                for model in models
            ], int(total or 0)

    async def list_chunks(
        self,
        document_id: int,
        *,
        offset: int,
        limit: int,
        section_public_id: UUID | None = None,
    ) -> tuple[List[ChunkRecord], int]:
        async with self._session.begin():
            filters = [DocumentChunkModel.document_id == document_id]
            if section_public_id is not None:
                filters.append(
                    DocumentChunkModel.section_id.in_(
                        select(DocumentSectionModel.section_id).where(
                            DocumentSectionModel.document_id == document_id,
                            DocumentSectionModel.public_id
                            == section_public_id,
                        )
                    )
                )
            total = await self._session.scalar(
                select(func.count())
                .select_from(DocumentChunkModel)
                .where(*filters)
            )
            rows = (
                await self._session.execute(
                    select(DocumentChunkModel, DocumentSectionModel)
                    .join(
                        DocumentSectionModel,
                        DocumentSectionModel.section_id
                        == DocumentChunkModel.section_id,
                    )
                    .where(*filters)
                    .order_by(DocumentChunkModel.position)
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
            return [
                ChunkRecord(
                    chunk_id=chunk.chunk_id,
                    public_id=chunk.public_id,
                    section_public_id=section.public_id,
                    section_title=section.title,
                    section_path=section.path,
                    chunk_index=chunk.chunk_index,
                    position=chunk.position,
                    content=chunk.content,
                    token_count=chunk.token_count,
                    start_page=chunk.start_page,
                    end_page=chunk.end_page,
                )
                for chunk, section in rows
            ], int(total or 0)


def _walk(node: SectionNode):
    yield node
    for child in node.children:
        yield from _walk(child)
