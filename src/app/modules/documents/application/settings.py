from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DocumentIngestionSettings:
    """Configuration snapshot passed into use cases (never read from env)."""

    max_upload_bytes: int
    max_pages: int
    chunk_target_tokens: int
    chunk_max_tokens: int
    chunk_min_tokens: int
    chunk_overlap_tokens: int
    parser_version: str
    chunking_version: str
    summary_version: str
    summary_input_max_tokens: int = 6000
