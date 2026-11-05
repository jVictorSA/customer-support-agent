from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from app.modules.documents.domain.content_block import ContentBlock


@dataclass(slots=True)
class SectionNode:
    """In-memory node of the document hierarchy."""

    title: str
    level: int
    number: str | None
    position: int
    path: str
    public_id: UUID = field(default_factory=uuid4)
    blocks: list[ContentBlock] = field(default_factory=list)
    children: list["SectionNode"] = field(default_factory=list)
    summary: str | None = None
    summary_embedding: list[float] | None = None
    token_count: int = 0

    @property
    def content(self) -> str:
        return "\n\n".join(
            block.text for block in self.blocks if block.text.strip()
        )

    @property
    def start_page(self) -> int:
        pages = [block.page_start for block in self.blocks]
        if not pages and self.children:
            return min(child.start_page for child in self.children)
        return min(pages) if pages else 1

    @property
    def end_page(self) -> int:
        pages = [block.page_end for block in self.blocks]
        if self.children:
            pages.append(max(child.end_page for child in self.children))
        return max(pages) if pages else self.start_page


@dataclass(frozen=True, slots=True)
class DocumentSection:
    section_id: int | None
    public_id: UUID
    document_id: int
    parent_section_id: int | None
    parent_public_id: UUID | None
    section_number: str | None
    title: str
    level: int
    path: str
    position: int
    content: str
    summary: str | None
    summary_embedding: list[float] | None
    token_count: int
    start_page: int
    end_page: int
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
