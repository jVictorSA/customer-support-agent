from app.core.exceptions import NotFoundError


class ConversationNotFoundError(NotFoundError):
    code = "conversation_not_found"
    message = "Conversation not found"

    def __init__(self) -> None:
        super().__init__("Conversation not found")
