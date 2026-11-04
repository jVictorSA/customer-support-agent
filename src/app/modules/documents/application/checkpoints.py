import hashlib
import json
from dataclasses import asdict

from app.modules.documents.application.interfaces import DocumentStorage
from app.modules.documents.domain.content_block import (
    BlockType,
    ContentBlock,
)
from app.modules.documents.domain.parsed_document import ParsedDocument
from app.modules.documents.domain.token_counter import TokenCounter


def parsed_key(checksum: str, parser_version: str) -> str:
    return f"cache/{checksum}/parsed-{parser_version}.json"


def summaries_key(checksum: str, summary_version: str) -> str:
    return f"cache/{checksum}/summaries-{summary_version}.json"


def embeddings_prefix(checksum: str, model: str, dimensions: int) -> str:
    return f"cache/{checksum}/embeddings-{model}-{dimensions}/"


def text_hash(text: str, *, model: str, dimensions: int) -> str:
    payload = f"{model}:{dimensions}:{text}".encode()
    return hashlib.sha256(payload).hexdigest()


async def load_parsed(
    storage: DocumentStorage, *, checksum: str, parser_version: str
) -> ParsedDocument | None:
    raw = await storage.get_checkpoint(
        key=parsed_key(checksum, parser_version)
    )
    if raw is None:
        return None
    payload = json.loads(raw.decode("utf-8"))
    blocks = tuple(
        ContentBlock(
            block_type=BlockType(item["block_type"]),
            text=item["text"],
            page_start=int(item["page_start"]),
            page_end=int(item["page_end"]),
            position=int(item["position"]),
            heading_level=item.get("heading_level"),
        )
        for item in payload["blocks"]
    )
    return ParsedDocument(
        title=payload["title"],
        total_pages=int(payload["total_pages"]),
        blocks=blocks,
        parser_version=payload["parser_version"],
        metadata=payload.get("metadata", {}),
    )


async def save_parsed(
    storage: DocumentStorage,
    *,
    checksum: str,
    parsed: ParsedDocument,
) -> None:
    payload = {
        "title": parsed.title,
        "total_pages": parsed.total_pages,
        "parser_version": parsed.parser_version,
        "metadata": parsed.metadata,
        "blocks": [
            {
                **asdict(block),
                "block_type": block.block_type.value,
            }
            for block in parsed.blocks
        ],
    }
    await storage.put_checkpoint(
        key=parsed_key(checksum, parsed.parser_version),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    )


async def load_summaries(
    storage: DocumentStorage, *, checksum: str, summary_version: str
) -> dict[str, str]:
    raw = await storage.get_checkpoint(
        key=summaries_key(checksum, summary_version)
    )
    return json.loads(raw.decode("utf-8")) if raw else {}


async def save_summaries(
    storage: DocumentStorage,
    *,
    checksum: str,
    summary_version: str,
    summaries: dict[str, str],
) -> None:
    await storage.put_checkpoint(
        key=summaries_key(checksum, summary_version),
        data=json.dumps(summaries, ensure_ascii=False).encode("utf-8"),
    )


async def load_embeddings(
    storage: DocumentStorage, *, checksum: str, model: str, dimensions: int
) -> dict[str, list[float]]:
    prefix = embeddings_prefix(checksum, model, dimensions)
    keys = await storage.list_checkpoints(prefix=prefix)
    cached: dict[str, list[float]] = {}
    for key in keys:
        raw = await storage.get_checkpoint(key=key)
        if raw is None:
            continue
        for line in raw.decode("utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            cached[item["hash"]] = item["vector"]
    return cached


async def save_embedding_batch(
    storage: DocumentStorage,
    *,
    checksum: str,
    model: str,
    dimensions: int,
    batch_index: int,
    hashes: list[str],
    vectors: list[list[float]],
) -> None:
    prefix = embeddings_prefix(checksum, model, dimensions)
    lines = [
        json.dumps({"hash": digest, "vector": vector})
        for digest, vector in zip(hashes, vectors, strict=True)
    ]
    key = f"{prefix}{batch_index:05d}-{hashes[0][:12] if hashes else 'empty'}.jsonl"
    await storage.put_checkpoint(
        key=key, data=("\n".join(lines) + "\n").encode("utf-8")
    )


def batch_texts(
    items: list[tuple[str, str]],
    *,
    max_items: int,
    max_tokens: int,
    counter: TokenCounter,
) -> list[list[tuple[str, str]]]:
    batches: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    current_tokens = 0
    for digest, text in items:
        tokens = counter.count(text)
        if current and (
            len(current) >= max_items or current_tokens + tokens > max_tokens
        ):
            batches.append(current)
            current = []
            current_tokens = 0
        current.append((digest, text))
        current_tokens += tokens
    if current:
        batches.append(current)
    return batches



