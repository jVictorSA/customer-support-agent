from app.core.exceptions import AppError, ConflictError, NotFoundError


class MessageNotFoundError(NotFoundError):
    code = "message_not_found"
    message = "Message not found"


class ConversationUnavailableError(NotFoundError):
    code = "conversation_not_found"
    message = "Conversation not found"


class ConversationBusyError(ConflictError):
    code = "conversation_busy"
    message = "The previous message is still being processed"


class ClientMessageIdConflictError(ConflictError):
    code = "client_message_id_conflict"
    message = "client_message_id was already used with different content"


class MessageQueueUnavailableError(AppError):
    code = "message_queue_unavailable"
    message = "Message was accepted but could not be queued"
    status_code = 503


class InvalidWebhookUrlError(AppError):
    code = "invalid_webhook_url"
    message = "webhook_url must be a valid http(s) URL"
    status_code = 422
