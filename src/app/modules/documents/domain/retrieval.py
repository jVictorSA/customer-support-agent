from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RetrievedPassage:
    document_public_id: UUID
    document_name: str
    section_public_id: UUID
    section_title: str
    section_path: str
    chunk_public_id: UUID
    content: str
    score: float
    start_page: int
    end_page: int

    @property
    def citation_reference(self) -> str:
        return f"knowledge:{self.chunk_public_id}"


@dataclass(frozen=True, slots=True)
class KnowledgeSearchSettings:
    vector_top_k: int = 20
    lexical_top_k: int = 20
    rrf_k: int = 60
    final_k: int = 8
    context_max_tokens: int = 6000
