from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PreparedUpload:
    """A PDF already streamed to disk and inspected by the presentation layer."""

    original_filename: str
    content_type: str
    size_bytes: int
    checksum: str
    page_count: int
    temp_path: Path
