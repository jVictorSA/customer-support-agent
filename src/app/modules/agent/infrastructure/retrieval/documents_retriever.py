from app.modules.agent.domain.results import KnowledgePassage
from app.modules.documents.application.search_knowledge import (
    SearchKnowledgeUseCase,
)


class DocumentsKnowledgeRetriever:
    def __init__(self, use_case: SearchKnowledgeUseCase) -> None:
        self._use_case = use_case

    async def search(
        self, query: str, *, limit: int | None = None
    ) -> list[KnowledgePassage]:
        passages = await self._use_case.execute(query, final_k=limit)
        return [
            KnowledgePassage(
                reference=passage.citation_reference,
                title=passage.section_title,
                path=passage.section_path,
                content=passage.content,
                score=passage.score,
                document_name=passage.document_name,
            )
            for passage in passages
        ]
