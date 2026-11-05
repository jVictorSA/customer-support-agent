import tiktoken

from app.modules.documents.domain.token_counter import TokenCounter


class TiktokenTokenCounter(TokenCounter):
    """Approximate token counting independent from the embedding provider."""

    def __init__(self, encoding_name: str = "o200k_base") -> None:
        self._encoding = tiktoken.get_encoding(encoding_name)

    def count(self, text: str) -> int:
        if not text:
            return 0
        return len(self._encoding.encode(text, disallowed_special=()))
