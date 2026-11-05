from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.domain.retrieval import RetrievedPassage
from app.modules.documents.domain.document_status import DocumentStatus
from app.modules.documents.infrastructure.models import (
    DocumentChunkModel,
    DocumentModel,
    DocumentSectionModel,
)


class SqlAlchemyKnowledgeSearchRepository:
    """Hybrid chunk retrieval with parent/child context expansion."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def hybrid_search(
        self,
        *,
        query_text: str,
        query_embedding: list[float],
        vector_top_k: int,
        lexical_top_k: int,
        rrf_k: int,
        final_k: int,
        context_max_tokens: int,
    ) -> list[RetrievedPassage]:
        async with self._session.begin():
            document_filters = (
                DocumentModel.status == DocumentStatus.COMPLETED,
                DocumentModel.is_enabled.is_(True),
                DocumentModel.deleted_at.is_(None),
            )

            distance = DocumentChunkModel.embedding.cosine_distance(
                query_embedding
            )
            dense_rows = (
                await self._session.execute(
                    select(DocumentChunkModel.chunk_id, distance)
                    .join(
                        DocumentModel,
                        DocumentModel.document_id
                        == DocumentChunkModel.document_id,
                    )
                    .where(
                        *document_filters,
                        DocumentChunkModel.embedding.is_not(None),
                    )
                    .order_by(distance)
                    .limit(vector_top_k)
                )
            ).all()

            tsquery = func.plainto_tsquery("portuguese", query_text)
            rank = func.ts_rank_cd(
                DocumentChunkModel.search_vector, tsquery
            )
            lexical_rows = (
                await self._session.execute(
                    select(DocumentChunkModel.chunk_id, rank)
                    .join(
                        DocumentModel,
                        DocumentModel.document_id
                        == DocumentChunkModel.document_id,
                    )
                    .where(
                        *document_filters,
                        DocumentChunkModel.search_vector.op("@@")(tsquery),
                    )
                    .order_by(rank.desc())
                    .limit(lexical_top_k)
                )
            ).all()

            scores: dict[int, float] = {}
            for rows in (dense_rows, lexical_rows):
                for position, (chunk_id, _) in enumerate(rows, start=1):
                    scores[chunk_id] = scores.get(chunk_id, 0.0) + (
                        1.0 / (rrf_k + position)
                    )

            if not scores:
                return []

            ranked_ids = sorted(
                scores, key=lambda chunk_id: scores[chunk_id], reverse=True
            )
            rows = (
                await self._session.execute(
                    select(
                        DocumentChunkModel,
                        DocumentSectionModel,
                        DocumentModel,
                    )
                    .join(
                        DocumentSectionModel,
                        DocumentSectionModel.section_id
                        == DocumentChunkModel.section_id,
                    )
                    .join(
                        DocumentModel,
                        DocumentModel.document_id
                        == DocumentChunkModel.document_id,
                    )
                    .where(DocumentChunkModel.chunk_id.in_(ranked_ids))
                )
            ).all()
            by_chunk = {
                chunk.chunk_id: (chunk, section, document)
                for chunk, section, document in rows
            }

            # Keep the best chunk of each section, preserving rank order.
            selected_sections: list[tuple[DocumentChunkModel, object, object]]
            selected_sections = []
            seen_sections: set[int] = set()
            for chunk_id in ranked_ids:
                item = by_chunk.get(chunk_id)
                if item is None:
                    continue
                chunk, section, document = item
                if section.section_id in seen_sections:
                    continue
                seen_sections.add(section.section_id)
                selected_sections.append((chunk, section, document))
                if len(selected_sections) >= final_k:
                    break

            parent_ids = {
                section.parent_section_id
                for _, section, _ in selected_sections
                if section.parent_section_id is not None
            }
            parents = {}
            if parent_ids:
                parent_rows = (
                    await self._session.scalars(
                        select(DocumentSectionModel).where(
                            DocumentSectionModel.section_id.in_(parent_ids)
                        )
                    )
                ).all()
                parents = {
                    parent.section_id: parent for parent in parent_rows
                }

            passages: list[RetrievedPassage] = []
            used_tokens = 0
            for chunk, section, document in selected_sections:
                parent = parents.get(section.parent_section_id)
                body = section.content.strip() or chunk.content.strip()
                header = _header(section, parent)
                content = f"{header}\n\n{body}" if body else header
                tokens = max(1, len(content) // 4)
                if passages and used_tokens + tokens > context_max_tokens:
                    body = chunk.content.strip()
                    content = f"{header}\n\n{body}" if body else header
                    tokens = max(1, len(content) // 4)
                if passages and used_tokens + tokens > context_max_tokens:
                    continue
                used_tokens += tokens
                passages.append(
                    RetrievedPassage(
                        document_public_id=document.public_id,
                        document_name=document.name,
                        section_public_id=section.public_id,
                        section_title=section.title,
                        section_path=section.path,
                        chunk_public_id=chunk.public_id,
                        content=content,
                        score=scores.get(chunk.chunk_id, 0.0),
                        start_page=chunk.start_page,
                        end_page=chunk.end_page,
                    )
                )
            return passages


def _header(section, parent) -> str:
    parts = [f"Seção: {section.title}", f"Caminho: {section.path}"]
    if parent is not None:
        parts.append(f"Seção superior: {parent.title}")
        if parent.summary:
            parts.append(f"Resumo da seção superior: {parent.summary}")
    return "\n".join(parts)
