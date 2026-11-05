import os
from uuid import uuid4

import pytest

from app.modules.documents.domain.document_status import DocumentStatus
from app.modules.documents.infrastructure.knowledge_search import (
    SqlAlchemyKnowledgeSearchRepository,
)
from app.modules.documents.infrastructure.models import (
    DocumentChunkModel,
    DocumentModel,
    DocumentSectionModel,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION_TESTS") != "1",
        reason="set RUN_INTEGRATION_TESTS=1 to run integration tests",
    ),
]


async def test_hybrid_retrieval_expands_section(integration_session) -> None:
    session = integration_session
    document = DocumentModel(
        public_id=uuid4(),
        name="Políticas da loja",
        source_filename="politicas.pdf",
        source_content_type="application/pdf",
        source_size_bytes=100,
        source_checksum=uuid4().hex,
        storage_key="sources/politicas.pdf",
        status=DocumentStatus.COMPLETED,
        is_enabled=True,
        total_pages=1,
        section_count=1,
        chunk_count=1,
    )
    session.add(document)
    await session.flush()

    section = DocumentSectionModel(
        public_id=uuid4(),
        document_id=document.document_id,
        title="Trocas e devoluções",
        level=1,
        path="1",
        position=0,
        content="Trocas e devoluções podem ser solicitadas em até 7 dias.",
        summary="Regras de troca e devolução.",
        token_count=20,
        start_page=1,
        end_page=1,
    )
    session.add(section)
    await session.flush()

    embedding = [0.0] * 1024
    embedding[0] = 1.0
    session.add(
        DocumentChunkModel(
            public_id=uuid4(),
            document_id=document.document_id,
            section_id=section.section_id,
            chunk_index=0,
            position=0,
            content="Trocas e devoluções em até 7 dias corridos.",
            embedding_text="Trocas e devoluções em até 7 dias corridos.",
            content_hash=uuid4().hex,
            embedding_text_hash=uuid4().hex,
            embedding=embedding,
            token_count=12,
            start_page=1,
            end_page=1,
        )
    )
    await session.commit()

    repository = SqlAlchemyKnowledgeSearchRepository(session)
    passages = await repository.hybrid_search(
        query_text="trocas devoluções",
        query_embedding=embedding,
        vector_top_k=10,
        lexical_top_k=10,
        rrf_k=60,
        final_k=5,
        context_max_tokens=1000,
    )

    assert len(passages) == 1
    assert passages[0].section_title == "Trocas e devoluções"
    assert "7 dias" in passages[0].content
    assert passages[0].document_public_id == document.public_id
