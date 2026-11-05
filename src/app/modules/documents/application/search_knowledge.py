from app.modules.documents.application.interfaces import EmbeddingProvider
from app.modules.documents.application.retrieval import (
    KnowledgeSearchRepository,
)
from app.modules.documents.domain.retrieval import (
    KnowledgeSearchSettings,
    RetrievedPassage,
)


class SearchKnowledgeUseCase:
    def __init__(
        self,
        *,
        embedder: EmbeddingProvider,
        repository: KnowledgeSearchRepository,
        settings: KnowledgeSearchSettings,
    ) -> None:
        self._embedder = embedder
        self._repository = repository
        self._settings = settings

    async def execute(
        self, query: str, *, final_k: int | None = None
    ) -> list[RetrievedPassage]:
        query_embedding = await self._embedder.embed_query(query)
        return await self._repository.hybrid_search(
            query_text=query,
            query_embedding=query_embedding,
            vector_top_k=self._settings.vector_top_k,
            lexical_top_k=self._settings.lexical_top_k,
            rrf_k=self._settings.rrf_k,
            final_k=final_k or self._settings.final_k,
            context_max_tokens=self._settings.context_max_tokens,
        )
