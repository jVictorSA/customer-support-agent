import httpx
import pytest

from app.modules.documents.application.exceptions import (
    EmbeddingProviderError,
)
from app.modules.documents.infrastructure.embeddings.jina_embedder import (
    JinaEmbeddingProvider,
)


def provider(handler, *, max_retries: int = 3) -> JinaEmbeddingProvider:
    return JinaEmbeddingProvider(
        api_key="test-key",
        base_url="https://example.test/v1",
        model="fake-embedding",
        dimensions=2,
        timeout=5,
        max_retries=max_retries,
        rpm=1000,
        tpm=1_000_000,
        transport=httpx.MockTransport(handler),
    )


async def test_retries_rate_limit_and_returns_vectors() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                429, headers={"Retry-After": "0"}, json={"detail": "slow"}
            )
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2]}]})

    vectors = await provider(handler).embed_passages(["texto"])

    assert calls == 2
    assert vectors == [[0.1, 0.2]]


async def test_does_not_retry_auth_errors() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, json={"detail": "unauthorized"})

    with pytest.raises(EmbeddingProviderError):
        await provider(handler).embed_passages(["texto"])

    assert calls == 1


async def test_rejects_wrong_vector_dimensions() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"embedding": [0.1]}]})

    with pytest.raises(EmbeddingProviderError):
        await provider(handler).embed_passages(["texto"])
