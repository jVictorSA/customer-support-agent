from typing import Protocol


class TokenCounter(Protocol):
    """Counts model tokens for a piece of text."""

    def count(self, text: str) -> int: ...
