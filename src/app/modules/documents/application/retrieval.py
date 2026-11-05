from typing import Protocol

from app.modules.documents.domain.retrieval import RetrievedPassage


class KnowledgeSearchRepository(Protocol):
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
    ) -> list[RetrievedPassage]: ...
