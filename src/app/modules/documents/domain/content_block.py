from dataclasses import dataclass
from enum import StrEnum


class BlockType(StrEnum):
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    LIST = "list"
    TABLE = "table"
    CAPTION = "caption"
    CODE = "code"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class ContentBlock:
    """A structural unit extracted from the source document."""

    block_type: BlockType
    text: str
    page_start: int
    page_end: int
    position: int
    heading_level: int | None = None

    @property
    def is_heading(self) -> bool:
        return self.block_type is BlockType.HEADING
