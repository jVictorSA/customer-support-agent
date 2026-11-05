import logging

logger = logging.getLogger(__name__)


class AgentTokenCounter:
    """Token counter with a safe fallback when tiktoken is unavailable."""

    def __init__(self, encoding_name: str = "o200k_base") -> None:
        self._encoding = None
        try:
            import tiktoken

            self._encoding = tiktoken.get_encoding(encoding_name)
        except Exception:
            logger.warning(
                "tiktoken is unavailable; using approximate token counts"
            )

    def count(self, text: str) -> int:
        if not text:
            return 0
        if self._encoding is not None:
            return len(self._encoding.encode(text, disallowed_special=()))
        return max(1, len(text) // 4)
