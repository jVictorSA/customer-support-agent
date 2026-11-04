import hashlib
import re

from app.modules.documents.domain.chunk import ChunkDraft
from app.modules.documents.domain.content_block import (
    BlockType,
    ContentBlock,
)
from app.modules.documents.domain.section import SectionNode
from app.modules.documents.domain.section_tree import (
    nearest_ancestor_summary,
    section_path_titles,
)
from app.modules.documents.domain.token_counter import TokenCounter

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_embedding_text(
    *,
    document_title: str,
    section_path: str,
    parent_summary: str | None,
    content: str,
) -> str:
    lines = [f"Document: {document_title}"]
    if section_path:
        lines.append(f"Path: {section_path}")
    if parent_summary:
        lines.append(f"Section summary: {parent_summary}")
    lines.append("Content:")
    lines.append(content)
    return "\n".join(lines)


class SectionChunker:
    """Split one section's direct content without ever crossing its boundary."""

    def __init__(
        self,
        counter: TokenCounter,
        *,
        target_tokens: int = 800,
        max_tokens: int = 1000,
        min_tokens: int = 150,
        overlap_tokens: int = 60,
    ) -> None:
        self._counter = counter
        self._target = target_tokens
        self._max = max_tokens
        self._min = min_tokens
        self._overlap = overlap_tokens

    def chunk(
        self,
        *,
        root: SectionNode,
        section: SectionNode,
        document_title: str,
    ) -> list[ChunkDraft]:
        pieces = self._group_blocks(section.blocks)
        pieces = self._merge_small(pieces)
        if not pieces:
            return []

        path = section_path_titles(root, section)
        parent_summary = nearest_ancestor_summary(root, section)
        contents = [text for text, _, _ in pieces]
        drafts: list[ChunkDraft] = []

        for index, (content, start_page, end_page) in enumerate(pieces):
            prefix = ""
            suffix = ""
            if index > 0:
                prefix = _take_tail(contents[index - 1], self._overlap, self._counter)
            if index + 1 < len(contents):
                suffix = _take_head(contents[index + 1], self._overlap, self._counter)
            embedding_content = "\n".join(
                part for part in (prefix, content, suffix) if part
            )
            embedding_text = build_embedding_text(
                document_title=document_title,
                section_path=path,
                parent_summary=parent_summary,
                content=embedding_content,
            )
            drafts.append(
                ChunkDraft(
                    chunk_index=index,
                    content=content,
                    embedding_text=embedding_text,
                    token_count=self._counter.count(content),
                    start_page=start_page,
                    end_page=end_page,
                    content_hash=_sha256(content),
                    embedding_text_hash=_sha256(embedding_text),
                )
            )
        return drafts

    def _group_blocks(
        self, blocks: list[ContentBlock]
    ) -> list[tuple[str, int, int]]:
        pieces: list[tuple[str, int, int]] = []
        current: list[ContentBlock] = []

        def flush() -> None:
            if not current:
                return
            text = "\n\n".join(block.text for block in current if block.text.strip())
            if text.strip():
                pieces.append(
                    (
                        text,
                        min(block.page_start for block in current),
                        max(block.page_end for block in current),
                    )
                )
            current.clear()

        for block in blocks:
            text = block.text.strip()
            if not text:
                continue
            block_tokens = self._counter.count(text)
            if block_tokens > self._max:
                flush()
                for part in self._split_oversized(block):
                    pieces.append((part, block.page_start, block.page_end))
                continue

            candidate_tokens = self._counter.count(
                "\n\n".join([*(b.text for b in current), text])
            )
            if current and (
                candidate_tokens > self._max or candidate_tokens > self._target
            ):
                flush()
            current.append(block)
        flush()
        return pieces

    def _split_oversized(self, block: ContentBlock) -> list[str]:
        text = block.text.strip()
        header = ""
        if block.block_type is BlockType.TABLE:
            lines = text.splitlines()
            if lines and lines[0].lstrip().startswith("|"):
                header = "\n".join(lines[:2]) + "\n"
        parts = self._split_text(text, header=header)
        return [part for part in parts if part.strip()]

    def _split_text(self, text: str, *, header: str = "") -> list[str]:
        if self._counter.count(text) <= self._max:
            return [text]
        for separator in ("\n\n", "\n", ". ", " "):
            pieces = self._split_on(text, separator)
            if len(pieces) == 1:
                continue
            result: list[str] = []
            for piece in pieces:
                if self._counter.count(header + piece) > self._max:
                    result.extend(self._split_text(piece, header=header))
                else:
                    result.append((header + piece) if header else piece)
            return result
        # Last resort: hard word windows.
        words = text.split()
        result = []
        current: list[str] = []
        for word in words:
            candidate = " ".join([*current, word])
            if current and self._counter.count(header + candidate) > self._max:
                result.append(header + " ".join(current) if header else " ".join(current))
                current = [word]
            else:
                current.append(word)
        if current:
            joined = " ".join(current)
            result.append(header + joined if header else joined)
        return result

    def _split_on(self, text: str, separator: str) -> list[str]:
        if separator == ". ":
            chunks = [part + "." for part in _SENTENCE_SPLIT.split(text) if part]
            return chunks
        return [part for part in text.split(separator) if part]

    def _merge_small(
        self, pieces: list[tuple[str, int, int]]
    ) -> list[tuple[str, int, int]]:
        if len(pieces) <= 1:
            return pieces
        merged: list[tuple[str, int, int]] = []
        index = 0
        while index < len(pieces):
            text, start, end = pieces[index]
            if (
                merged
                and self._counter.count(text) < self._min
                and self._counter.count(merged[-1][0] + "\n\n" + text) <= self._max
            ):
                previous_text, previous_start, _ = merged[-1]
                merged[-1] = (
                    previous_text + "\n\n" + text,
                    previous_start,
                    end,
                )
                index += 1
                continue
            if (
                self._counter.count(text) < self._min
                and index + 1 < len(pieces)
                and self._counter.count(
                    text + "\n\n" + pieces[index + 1][0]
                )
                <= self._max
            ):
                next_text, _, next_end = pieces[index + 1]
                merged.append((text + "\n\n" + next_text, start, next_end))
                index += 2
                continue
            merged.append((text, start, end))
            index += 1
        return merged


def _take_head(text: str, token_budget: int, counter: TokenCounter) -> str:
    if token_budget <= 0:
        return ""
    words = text.split()
    taken: list[str] = []
    for word in words:
        candidate = " ".join([*taken, word])
        if counter.count(candidate) > token_budget:
            break
        taken.append(word)
    return " ".join(taken)


def _take_tail(text: str, token_budget: int, counter: TokenCounter) -> str:
    if token_budget <= 0:
        return ""
    words = text.split()
    taken: list[str] = []
    for word in reversed(words):
        candidate = " ".join([word, *taken])
        if counter.count(candidate) > token_budget:
            break
        taken.insert(0, word)
    return " ".join(taken)
