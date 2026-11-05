from app.modules.documents.application.search_knowledge import (
    SearchKnowledgeUseCase,
)
from app.modules.documents.domain.retrieval import (
    KnowledgeSearchSettings,
    RetrievedPassage,
)
from uuid import uuid4


class FakeEmbedder:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def embed_passages(self, texts):
        return [[0.0] for _ in texts]

    async def embed_query(self, text: str):
        self.queries.append(text)
        return [1.0, 0.0]


class FakeRepository:
    def __init__(self) -> None:
        self.kwargs = {}

    async def hybrid_search(self, **kwargs):
        self.kwargs = kwargs
        return [
            RetrievedPassage(
                document_public_id=uuid4(),
                document_name="Políticas",
                section_public_id=uuid4(),
                section_title="Trocas",
                section_path="1",
                chunk_public_id=uuid4(),
                content="Trocas em até 7 dias.",
                score=0.5,
                start_page=1,
                end_page=1,
            )
        ]


async def test_search_knowledge_embeds_query_and_forwards_settings() -> None:
    embedder = FakeEmbedder()
    repository = FakeRepository()
    use_case = SearchKnowledgeUseCase(
        embedder=embedder,
        repository=repository,
        settings=KnowledgeSearchSettings(
            vector_top_k=5,
            lexical_top_k=6,
            rrf_k=60,
            final_k=3,
            context_max_tokens=1000,
        ),
    )

    passages = await use_case.execute("política de troca")

    assert embedder.queries == ["política de troca"]
    assert repository.kwargs["query_embedding"] == [1.0, 0.0]
    assert repository.kwargs["final_k"] == 3
    assert len(passages) == 1
