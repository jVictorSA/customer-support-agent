import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from app.modules.documents.domain.chunk import ChunkDraft
from app.modules.documents.domain.document import Document
from app.modules.documents.domain.document_status import DocumentStatus
from app.modules.documents.domain.section import SectionNode
from app.modules.documents.infrastructure.models import (
    DocumentChunkModel,
)
from app.modules.documents.infrastructure.repository import (
    SqlAlchemyDocumentRepository,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="set RUN_INTEGRATION_TESTS=1 to run integration tests",
    ),
]


async def test_document_persistence_pgvector_ltree_and_fts(
    integration_session,
) -> None:
    repository = SqlAlchemyDocumentRepository(integration_session)
    now = datetime(2026, 11, 4, tzinfo=UTC)
    document = await repository.create(
        Document(
            document_id=None,
            public_id=uuid4(),
            name="Políticas",
            source_filename="politicas.pdf",
            source_content_type="application/pdf",
            source_size_bytes=10,
            source_checksum="b" * 64,
            storage_key="sources/" + "b" * 64 + ".pdf",
            status=DocumentStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
    )

    root = SectionNode(
        title="Políticas",
        level=0,
        number=None,
        position=0,
        path="n0",
        summary="Resumo geral",
        summary_embedding=[0.1] * 1024,
    )
    child = SectionNode(
        title="Trocas",
        level=1,
        number="1",
        position=1,
        path="n0.n1",
    )
    root.children.append(child)
    draft = ChunkDraft(
        chunk_index=0,
        content="O prazo para troca é de sete dias corridos.",
        embedding_text="Document: Políticas\nContent:\nO prazo para troca...",
        token_count=9,
        start_page=1,
        end_page=1,
        content_hash="c" * 64,
        embedding_text_hash="d" * 64,
        embedding=[0.1] * 1024,
    )

    await repository.replace_content(
        document_id=document.document_id,
        root=root,
        chunks={child.public_id: [draft]},
        total_pages=1,
        parser_version="test",
        chunking_version="test",
        summary_version="test",
        embedding_model="fake",
        embedding_dimensions=1024,
    )

    stored = await repository.get_by_public_id(document.public_id)
    assert stored is not None
    assert stored.status is DocumentStatus.COMPLETED
    assert stored.section_count == 2
    assert stored.chunk_count == 1

    sections, section_total = await repository.list_sections(
        document.document_id, offset=0, limit=10
    )
    chunks, chunk_total = await repository.list_chunks(
        document.document_id, offset=0, limit=10
    )
    assert section_total == 2
    assert sections[1].parent_public_id == root.public_id
    assert chunk_total == 1
    assert chunks[0].content.startswith("O prazo")

    vector = await integration_session.scalar(
        select(DocumentChunkModel.chunk_id)
        .where(DocumentChunkModel.document_id == document.document_id)
        .order_by(DocumentChunkModel.embedding.cosine_distance([0.1] * 1024))
        .limit(1)
    )
    lexical = await integration_session.scalar(
        text(
            "SELECT chunk_id FROM document_chunks "
            "WHERE search_vector @@ plainto_tsquery('portuguese', 'troca') "
            "LIMIT 1"
        )
    )
    descendants = await integration_session.scalar(
        text(
            "SELECT count(*) FROM document_sections "
            "WHERE path <@ 'n0'::ltree"
        )
    )

    assert vector is not None
    assert lexical is not None
    assert descendants == 2
