from app.modules.documents.domain.chunker import SectionChunker
from app.modules.documents.domain.content_block import (
    BlockType,
    ContentBlock,
)
from app.modules.documents.domain.parsed_document import ParsedDocument
from app.modules.documents.domain.section_tree import (
    build_section_tree,
    flatten_sections,
)


class WordCounter:
    def count(self, text: str) -> int:
        return len(text.split())


def block(text: str, page: int = 1, kind: BlockType = BlockType.PARAGRAPH):
    return ContentBlock(
        block_type=kind,
        text=text,
        page_start=page,
        page_end=page,
        position=0,
        heading_level=1 if kind is BlockType.HEADING else None,
    )


def parsed(*blocks: ContentBlock) -> ParsedDocument:
    return ParsedDocument(
        title="Manual",
        total_pages=3,
        blocks=blocks,
        parser_version="test",
    )


def test_builds_synthetic_root_and_hierarchy() -> None:
    root = build_section_tree(
        parsed(
            block("Capa do manual"),
            block("1 Introdução", kind=BlockType.HEADING),
            block("Texto da introdução."),
            block("1.1 Contexto", kind=BlockType.HEADING),
            block("Texto do contexto."),
            block("2 Metodologia", kind=BlockType.HEADING),
            block("Texto da metodologia."),
        )
    )

    assert root.title == "Manual"
    assert root.level == 0
    assert root.content == "Capa do manual"
    assert [child.title for child in root.children] == [
        "Introdução",
        "Metodologia",
    ]
    introducao = root.children[0]
    assert introducao.number == "1"
    assert introducao.path == "n0.n1"
    assert introducao.children[0].title == "Contexto"
    assert introducao.children[0].path == "n0.n1.n1_1"
    assert [item.title for item in flatten_sections(root)] == [
        "Manual",
        "Introdução",
        "Contexto",
        "Metodologia",
    ]


def test_falls_back_to_single_root_without_headings() -> None:
    root = build_section_tree(parsed(block("Somente texto.")))
    assert root.children == []
    assert root.content == "Somente texto."


def test_chunks_never_cross_sections_and_overlap_is_embedding_only() -> None:
    root = build_section_tree(
        parsed(
            block("1 Primeira", kind=BlockType.HEADING),
            block("um dois tres quatro cinco seis"),
            block("sete oito nove dez onze doze"),
            block("2 Segunda", kind=BlockType.HEADING),
            block("treze quatorze quinze dezesseis"),
        )
    )
    chunker = SectionChunker(
        WordCounter(),
        target_tokens=7,
        max_tokens=10,
        min_tokens=1,
        overlap_tokens=3,
    )
    first = root.children[0]
    second = root.children[1]
    first_chunks = chunker.chunk(
        root=root, section=first, document_title="Manual"
    )
    second_chunks = chunker.chunk(
        root=root, section=second, document_title="Manual"
    )

    assert len(first_chunks) == 2
    assert first_chunks[0].content == "um dois tres quatro cinco seis"
    assert first_chunks[1].content == "sete oito nove dez onze doze"
    assert "sete oito nove" not in first_chunks[0].content
    assert "sete oito nove" in first_chunks[0].embedding_text
    assert "doze" not in second_chunks[0].embedding_text
    assert "treze" in second_chunks[0].content
    assert all(
        "treze" not in chunk.content for chunk in first_chunks
    )
