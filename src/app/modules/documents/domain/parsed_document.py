from dataclasses import dataclass, field
from typing import Any

from app.modules.documents.domain.content_block import ContentBlock


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    """Provider-independent representation of an extracted PDF."""

    title: str
    total_pages: int
    blocks: tuple[ContentBlock, ...]
    parser_version: str
    metadata: dict[str, Any] = field(default_factory=dict)
