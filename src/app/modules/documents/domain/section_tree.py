import re

from app.modules.documents.domain.content_block import (
    BlockType,
    ContentBlock,
)
from app.modules.documents.domain.parsed_document import ParsedDocument
from app.modules.documents.domain.section import SectionNode

SECTION_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s+(.+?)\s*$")
MAX_LABEL_LENGTH = 200


def _numbered_heading(block: ContentBlock) -> tuple[str, str, int] | None:
    match = SECTION_PATTERN.match(block.text.strip())
    if match is None or len(block.text.strip()) > 200:
        return None
    number, title = match.groups()
    if len(number.split(".")) > 6:
        return None
    return number, title, len(number.split("."))


def _heading_of(block: ContentBlock) -> tuple[str | None, str, int] | None:
    numbered = _numbered_heading(block)
    if block.block_type is not BlockType.HEADING:
        return numbered
    title = block.text.strip()
    if numbered is not None:
        number, numbered_title, numbered_level = numbered
        level = max(block.heading_level or 1, numbered_level)
        return number, numbered_title, level
    return None, title, max(block.heading_level or 1, 1)


def _normalize_label(number: str | None, position: int) -> str:
    if number:
        label = "n" + number.replace(".", "_")
    else:
        label = f"n{position}"
    return label[:MAX_LABEL_LENGTH]


def _unique_child_label(node: SectionNode, label: str) -> str:
    existing = {child.path.rsplit(".", 1)[-1] for child in node.children}
    if label not in existing:
        return label
    suffix = 2
    while f"{label}_{suffix}" in existing:
        suffix += 1
    return f"{label}_{suffix}"


def build_section_tree(parsed: ParsedDocument) -> SectionNode:
    """Build the document hierarchy, always rooted at a synthetic section.

    Headings split direct content; content before the first heading (cover,
    abstract, table of contents) belongs to the synthetic root. When no heading
    is detected the root simply contains the whole document.
    """
    root = SectionNode(
        title=parsed.title,
        level=0,
        number=None,
        position=0,
        path="n0",
    )
    stack: list[SectionNode] = [root]
    position = 1

    for block in parsed.blocks:
        heading = _heading_of(block)
        if heading is None:
            stack[-1].blocks.append(block)
            continue

        number, title, reported_level = heading
        level = min(max(reported_level, 1), stack[-1].level + 1)
        while len(stack) > 1 and stack[-1].level >= level:
            stack.pop()

        parent = stack[-1]
        label = _unique_child_label(
            parent, _normalize_label(number, position)
        )
        node = SectionNode(
            title=title,
            level=level,
            number=number,
            position=position,
            path=f"{parent.path}.{label}",
        )
        parent.children.append(node)
        stack.append(node)
        position += 1

    _assign_positions(root, counter=[0])
    return root


def _assign_positions(node: SectionNode, *, counter: list[int]) -> None:
    node.position = counter[0]
    counter[0] += 1
    for child in node.children:
        _assign_positions(child, counter=counter)


def flatten_sections(root: SectionNode) -> list[SectionNode]:
    """Return sections in document order."""
    result: list[SectionNode] = []
    _flatten(root, result)
    return result


def _flatten(node: SectionNode, result: list[SectionNode]) -> None:
    result.append(node)
    for child in node.children:
        _flatten(child, result)


def ancestors_of(root: SectionNode, target: SectionNode) -> list[SectionNode]:
    """Return ancestors from the root down to the direct parent of target."""
    path: list[SectionNode] = []

    def walk(node: SectionNode) -> bool:
        if node is target:
            return True
        for child in node.children:
            if walk(child):
                path.append(node)
                return True
        return False

    walk(root)
    return list(reversed(path))


def section_path_titles(root: SectionNode, target: SectionNode) -> str:
    """Return the human-readable ancestor path for prompts and embeddings."""
    titles = [node.title for node in ancestors_of(root, target) if node.level > 0]
    if target.level > 0:
        titles.append(target.title)
    return " > ".join(titles)


def nearest_ancestor_summary(
    root: SectionNode, target: SectionNode
) -> str | None:
    """Return the closest ancestor summary, excluding the section itself."""
    for node in reversed(ancestors_of(root, target)):
        if node.summary:
            return node.summary
    return None
