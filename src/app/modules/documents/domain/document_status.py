from enum import StrEnum


class DocumentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingStage(StrEnum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PARSING = "parsing"
    CHUNKING = "chunking"
    SUMMARIZING = "summarizing"
    EMBEDDING = "embedding"
    PERSISTING = "persisting"
