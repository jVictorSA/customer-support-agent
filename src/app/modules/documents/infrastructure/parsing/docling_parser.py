import asyncio
import logging
from pathlib import Path
from typing import Any

from app.modules.documents.application.exceptions import (
    DocumentIngestionError,
)
from app.modules.documents.domain.content_block import (
    BlockType,
    ContentBlock,
)
from app.modules.documents.domain.parsed_document import ParsedDocument

logger = logging.getLogger(__name__)

_HEADING_LABELS = {"section_header", "title"}
_TABLE_LABELS = {"table"}
_LIST_LABELS = {"list_item", "list"}
_CAPTION_LABELS = {"caption"}
_CODE_LABELS = {"code"}


class DoclingPdfParser:
    def __init__(self, *, parser_version: str) -> None:
        self._parser_version = parser_version

    async def parse(
        self, *, path: Path, title: str, ocr_enabled: bool
    ) -> ParsedDocument:
        try:
            return await asyncio.to_thread(
                self._parse_with_docling, path, title, ocr_enabled
            )
        except DocumentIngestionError:
            raise
        except Exception:
            logger.exception(
                "Docling failed for %s; falling back to PyMuPDF", path.name
            )
            return await asyncio.to_thread(self._parse_with_pymupdf, path, title)

    def _parse_with_docling(
        self, path: Path, title: str, ocr_enabled: bool
    ) -> ParsedDocument:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import (
            PdfPipelineOptions,
        )
        from docling.document_converter import (
            DocumentConverter,
            PdfFormatOption,
        )

        options = PdfPipelineOptions()
        options.do_ocr = ocr_enabled
        options.do_table_structure = True
        if ocr_enabled:
            try:
                from docling.datamodel.pipeline_options import (
                    TesseractOcrOptions,
                )

                options.ocr_options = TesseractOcrOptions(
                    lang=["por", "eng"]
                )
            except Exception:
                logger.warning("Tesseract OCR options unavailable; using default")

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=options
                )
            }
        )
        result = converter.convert(str(path))
        document = result.document
        blocks: list[ContentBlock] = []
        position = 0
        for item, level in document.iterate_items():
            text = getattr(item, "text", None)
            label = str(getattr(item, "label", "")).lower()
            if label == "table":
                text = _export_table(item, document)
            if not text or not str(text).strip():
                continue
            page_start, page_end = _pages(item)
            block_type = _block_type(label)
            blocks.append(
                ContentBlock(
                    block_type=block_type,
                    text=str(text).strip(),
                    page_start=page_start,
                    page_end=page_end,
                    position=position,
                    heading_level=level if block_type is BlockType.HEADING else None,
                )
            )
            position += 1

        total_pages = len(getattr(document, "pages", {}) or {}) or _max_page(
            blocks
        )
        if not blocks:
            raise DocumentIngestionError(
                "no_extractable_text",
                "No extractable text was found in the PDF",
            )
        return ParsedDocument(
            title=title,
            total_pages=max(total_pages, 1),
            blocks=tuple(blocks),
            parser_version=self._parser_version,
            metadata={"parser": "docling"},
        )

    def _parse_with_pymupdf(self, path: Path, title: str) -> ParsedDocument:
        try:
            import pymupdf
        except ImportError:
            import fitz as pymupdf

        document = pymupdf.open(str(path))
        blocks: list[ContentBlock] = []
        position = 0
        try:
            for page_index, page in enumerate(document, start=1):
                for raw in page.get_text("blocks"):
                    text = (raw[4] or "").strip()
                    if not text:
                        continue
                    for paragraph in text.split("\n\n"):
                        paragraph = paragraph.strip()
                        if not paragraph:
                            continue
                        blocks.append(
                            ContentBlock(
                                block_type=BlockType.PARAGRAPH,
                                text=paragraph,
                                page_start=page_index,
                                page_end=page_index,
                                position=position,
                            )
                        )
                        position += 1
            total_pages = len(document)
        finally:
            document.close()
        if not blocks:
            raise DocumentIngestionError(
                "no_extractable_text",
                "No extractable text was found in the PDF",
            )
        return ParsedDocument(
            title=title,
            total_pages=total_pages,
            blocks=tuple(blocks),
            parser_version=self._parser_version,
            metadata={"parser": "pymupdf"},
        )


def _block_type(label: str) -> BlockType:
    if label in _HEADING_LABELS:
        return BlockType.HEADING
    if label in _TABLE_LABELS:
        return BlockType.TABLE
    if label in _LIST_LABELS:
        return BlockType.LIST
    if label in _CAPTION_LABELS:
        return BlockType.CAPTION
    if label in _CODE_LABELS:
        return BlockType.CODE
    return BlockType.PARAGRAPH


def _export_table(item: Any, document: Any) -> str:
    exporter = getattr(item, "export_to_markdown", None)
    if exporter is None:
        return str(getattr(item, "text", "") or "")
    for args in ((document,), ()):
        try:
            return str(exporter(*args))
        except TypeError:
            continue
    return str(getattr(item, "text", "") or "")


def _pages(item: Any) -> tuple[int, int]:
    provenance = getattr(item, "prov", None) or []
    pages = [
        int(getattr(entry, "page_no", 1) or 1)
        for entry in provenance
        if getattr(entry, "page_no", None)
    ]
    if not pages:
        return 1, 1
    return min(pages), max(pages)


def _max_page(blocks: list[ContentBlock]) -> int:
    return max((block.page_end for block in blocks), default=1)
