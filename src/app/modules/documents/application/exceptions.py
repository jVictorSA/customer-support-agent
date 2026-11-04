from uuid import UUID

from app.core.exceptions import AppError, ConflictError, NotFoundError


class DocumentNotFoundError(NotFoundError):
    code = "document_not_found"
    message = "Document not found"

    def __init__(self, identifier: object) -> None:
        super().__init__(f"Document {identifier} not found")


class DocumentChecksumConflictError(ConflictError):
    code = "document_checksum_conflict"
    message = "A document with the same content already exists"

    def __init__(self, public_id: UUID) -> None:
        super().__init__(
            f"A document with the same checksum already exists: {public_id}"
        )
        self.public_id = public_id


class DocumentProcessingConflictError(ConflictError):
    code = "document_processing_conflict"
    message = "Document is currently being processed"


class DocumentPayloadTooLargeError(AppError):
    code = "document_payload_too_large"
    message = "Document exceeds the maximum allowed size"
    status_code = 413


class DocumentUnsupportedMediaTypeError(AppError):
    code = "document_unsupported_media_type"
    message = "Only PDF documents are supported"
    status_code = 415


class DocumentUnprocessableError(AppError):
    code = "document_unprocessable"
    message = "The document could not be accepted for processing"
    status_code = 422


class DocumentQueueUnavailableError(AppError):
    code = "document_queue_unavailable"
    message = "The processing queue is unavailable"
    status_code = 503


class DocumentStorageUnavailableError(AppError):
    code = "document_storage_unavailable"
    message = "Document storage is unavailable"
    status_code = 503


class DocumentIngestionError(RuntimeError):
    """Internal ingestion failure; mapped to a safe document error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class EmbeddingProviderError(DocumentIngestionError):
    def __init__(self, message: str = "Embedding provider failed") -> None:
        super().__init__("embedding_provider_failed", message)


class SummaryGenerationError(DocumentIngestionError):
    def __init__(self, message: str = "Summary generation failed") -> None:
        super().__init__("summary_generation_failed", message)
