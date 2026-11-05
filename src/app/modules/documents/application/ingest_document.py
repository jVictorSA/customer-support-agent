import hashlib
import logging
import tempfile
from dataclasses import replace
from pathlib import Path
from uuid import UUID

from app.modules.documents.application.checkpoints import (
    batch_texts,
    load_embeddings,
    load_parsed,
    load_summaries,
    save_embedding_batch,
    save_parsed,
    save_summaries,
    text_hash,
)
from app.modules.documents.application.exceptions import (
    DocumentIngestionError,
)
from app.modules.documents.application.interfaces import (
    DocumentParser,
    DocumentRepository,
    DocumentStorage,
    EmbeddingProvider,
    SectionSummarizer,
)
from app.modules.documents.domain.settings import DocumentIngestionSettings
from app.modules.documents.domain.chunk import ChunkDraft
from app.modules.documents.domain.chunker import (
    SectionChunker,
    build_embedding_text,
)
from app.modules.documents.domain.document import Document
from app.modules.documents.domain.document_status import (
    DocumentStatus,
    ProcessingStage,
)
from app.modules.documents.domain.section import SectionNode
from app.modules.documents.domain.section_tree import (
    build_section_tree,
    flatten_sections,
    section_path_titles,
)
from app.modules.documents.domain.token_counter import TokenCounter

logger = logging.getLogger(__name__)


class IngestDocumentUseCase:
    def __init__(
        self,
        *,
        repository: DocumentRepository,
        storage: DocumentStorage,
        parser: DocumentParser,
        summarizer: SectionSummarizer,
        embedder: EmbeddingProvider,
        counter: TokenCounter,
        settings: DocumentIngestionSettings,
        ocr_enabled: bool,
        embedding_batch_size: int,
        embedding_batch_max_tokens: int,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._parser = parser
        self._summarizer = summarizer
        self._embedder = embedder
        self._counter = counter
        self._settings = settings
        self._ocr_enabled = ocr_enabled
        self._embedding_batch_size = embedding_batch_size
        self._embedding_batch_max_tokens = embedding_batch_max_tokens
        self._chunker = SectionChunker(
            counter,
            target_tokens=settings.chunk_target_tokens,
            max_tokens=settings.chunk_max_tokens,
            min_tokens=settings.chunk_min_tokens,
            overlap_tokens=settings.chunk_overlap_tokens,
        )

    async def execute(self, document_id: int) -> None:
        document = await self._repository.get_by_id(document_id)
        if document is None or document.deleted_at is not None:
            logger.info("Skipping missing or deleted document %s", document_id)
            return

        previous_status = document.status
        try:
            await self._run(document)
        except Exception as exc:
            code = (
                exc.code
                if isinstance(exc, DocumentIngestionError)
                else "ingestion_failed"
            )
            logger.exception(
                "Document ingestion failed for %s (%s)",
                document.public_id,
                code,
            )
            await self._repository.mark_failed(
                document_id,
                error_code=code,
                preserve_previous_status=previous_status
                is DocumentStatus.COMPLETED,
            )
            raise

    async def _run(self, document: Document) -> None:
        assert document.document_id is not None
        document_id = document.document_id
        checksum = document.source_checksum

        await self._repository.mark_processing(
            document_id, ProcessingStage.DOWNLOADING
        )
        with tempfile.TemporaryDirectory(prefix="documents-") as temp_dir:
            pdf_path = Path(temp_dir) / f"{checksum}.pdf"
            await self._storage.download_pdf(
                checksum=checksum, destination=pdf_path
            )

            await self._repository.mark_processing(
                document_id, ProcessingStage.PARSING
            )
            parsed = await load_parsed(
                self._storage,
                checksum=checksum,
                parser_version=self._settings.parser_version,
            )
            if parsed is None:
                parsed = await self._parser.parse(
                    path=pdf_path,
                    title=document.name,
                    ocr_enabled=self._ocr_enabled,
                )
                await save_parsed(
                    self._storage, checksum=checksum, parsed=parsed
                )

            await self._repository.mark_processing(
                document_id, ProcessingStage.CHUNKING
            )
            root = build_section_tree(parsed)
            chunks = self._chunk_tree(root, document_title=document.name)

            await self._repository.mark_processing(
                document_id, ProcessingStage.SUMMARIZING
            )
            await self._summarize_tree(root, document_title=document.name, checksum=checksum)

            await self._repository.mark_processing(
                document_id, ProcessingStage.EMBEDDING
            )
            chunks = await self._embed_tree(
                root=root,
                chunks=chunks,
                document_title=document.name,
                checksum=checksum,
            )

            await self._repository.mark_processing(
                document_id, ProcessingStage.PERSISTING
            )
            total_chunks = sum(len(items) for items in chunks.values())
            await self._repository.replace_content(
                document_id=document_id,
                root=root,
                chunks=chunks,
                total_pages=parsed.total_pages,
                parser_version=parsed.parser_version,
                chunking_version=self._settings.chunking_version,
                summary_version=self._summarizer.version,
                embedding_model=self._embedder.model,
                embedding_dimensions=self._embedder.dimensions,
            )
            logger.info(
                "Ingested document %s: %s sections, %s chunks",
                document.public_id,
                len(flatten_sections(root)),
                total_chunks,
            )

    def _chunk_tree(
        self, root: SectionNode, *, document_title: str
    ) -> dict[UUID, list[ChunkDraft]]:
        chunks: dict[UUID, list[ChunkDraft]] = {}
        for section in flatten_sections(root):
            drafts = self._chunker.chunk(
                root=root, section=section, document_title=document_title
            )
            if drafts:
                section.token_count = sum(item.token_count for item in drafts)
                chunks[section.public_id] = drafts
        return chunks

    async def _summarize_tree(
        self, root: SectionNode, *, document_title: str, checksum: str
    ) -> None:
        cached = await load_summaries(
            self._storage,
            checksum=checksum,
            summary_version=self._summarizer.version,
        )
        changed = False
        for section in reversed(flatten_sections(root)):
            if not section.children:
                continue
            max_chars = self._max_summary_chars()
            direct_content = _truncate(section.content, max_chars)
            child_summaries = [
                (
                    child.title,
                    _truncate(child.summary or child.content, max_chars // 3),
                )
                for child in section.children
                if (child.summary or child.content.strip())
            ]
            material = "\n\n".join(
                [direct_content, *(summary for _, summary in child_summaries)]
            )
            digest = hashlib.sha256(
                (
                    f"{self._summarizer.version}|{document_title}|"
                    f"{section_path_titles(root, section)}|{material}"
                ).encode()
            ).hexdigest()
            summary = cached.get(digest)
            if summary is None:
                summary = await self._summarizer.summarize(
                    document_title=document_title,
                    section_path=section_path_titles(root, section),
                    direct_content=direct_content,
                    child_summaries=child_summaries,
                )
                cached[digest] = summary
                changed = True
                await save_summaries(
                    self._storage,
                    checksum=checksum,
                    summary_version=self._summarizer.version,
                    summaries=cached,
                )
            section.summary = summary
        if changed:
            await save_summaries(
                self._storage,
                checksum=checksum,
                summary_version=self._summarizer.version,
                summaries=cached,
            )

    def _max_summary_chars(self) -> int:
        # Roughly four characters per token for the configured input budget.
        return 4 * self._settings.summary_input_max_tokens

    async def _embed_tree(
        self,
        *,
        root: SectionNode,
        chunks: dict[UUID, list[ChunkDraft]],
        document_title: str,
        checksum: str,
    ) -> dict[UUID, list[ChunkDraft]]:
        cached = await load_embeddings(
            self._storage,
            checksum=checksum,
            model=self._embedder.model,
            dimensions=self._embedder.dimensions,
        )

        wanted: dict[str, str] = {}
        for section in flatten_sections(root):
            if section.summary:
                section_embedding_text = build_embedding_text(
                    document_title=document_title,
                    section_path=section_path_titles(root, section),
                    parent_summary=None,
                    content=section.summary,
                )
                digest = text_hash(
                    section_embedding_text,
                    model=self._embedder.model,
                    dimensions=self._embedder.dimensions,
                )
                wanted[digest] = section_embedding_text
            for draft in chunks.get(section.public_id, []):
                digest = text_hash(
                    draft.embedding_text,
                    model=self._embedder.model,
                    dimensions=self._embedder.dimensions,
                )
                wanted[digest] = draft.embedding_text

        missing = [
            (digest, text)
            for digest, text in wanted.items()
            if digest not in cached
        ]
        batches = batch_texts(
            missing,
            max_items=self._embedding_batch_size,
            max_tokens=self._embedding_batch_max_tokens,
            counter=self._counter,
        )
        for index, batch in enumerate(batches):
            vectors = await self._embedder.embed_passages(
                [text for _, text in batch]
            )
            if len(vectors) != len(batch):
                raise DocumentIngestionError(
                    "embedding_provider_failed",
                    "Embedding provider returned an unexpected number of vectors",
                )
            for vector in vectors:
                if len(vector) != self._embedder.dimensions:
                    raise DocumentIngestionError(
                        "embedding_provider_failed",
                        "Embedding dimension does not match configuration",
                    )
            hashes = [digest for digest, _ in batch]
            await save_embedding_batch(
                self._storage,
                checksum=checksum,
                model=self._embedder.model,
                dimensions=self._embedder.dimensions,
                batch_index=index,
                hashes=hashes,
                vectors=vectors,
            )
            for digest, vector in zip(hashes, vectors, strict=True):
                cached[digest] = vector

        for section in flatten_sections(root):
            if section.summary:
                embedding_text = build_embedding_text(
                    document_title=document_title,
                    section_path=section_path_titles(root, section),
                    parent_summary=None,
                    content=section.summary,
                )
                section.summary_embedding = cached[
                    text_hash(
                        embedding_text,
                        model=self._embedder.model,
                        dimensions=self._embedder.dimensions,
                    )
                ]
            if section.public_id in chunks:
                chunks[section.public_id] = [
                    replace(
                        draft,
                        embedding=cached[
                            text_hash(
                                draft.embedding_text,
                                model=self._embedder.model,
                                dimensions=self._embedder.dimensions,
                            )
                        ],
                    )
                    for draft in chunks[section.public_id]
                ]
        return chunks


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit].rstrip() + "..."
