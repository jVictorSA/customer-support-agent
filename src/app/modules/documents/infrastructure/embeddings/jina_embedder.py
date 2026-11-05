import asyncio
import logging
import math
import random
import time
from collections import deque

import httpx

from app.modules.documents.application.exceptions import (
    EmbeddingProviderError,
)

logger = logging.getLogger(__name__)


class JinaEmbeddingProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        dimensions: int,
        timeout: float,
        max_retries: int,
        rpm: int,
        tpm: int,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._dimensions = dimensions
        self._timeout = timeout
        self._max_retries = max_retries
        self._limiter = _RateLimiter(rpm=rpm, tpm=tpm)
        self._transport = transport

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self._api_key:
            raise EmbeddingProviderError("JINA_API_KEY is not configured")

        await self._limiter.wait(tokens=sum(_estimate_tokens(text) for text in texts))
        last_error: Exception | None = None
        async with httpx.AsyncClient(
            timeout=self._timeout, transport=self._transport
        ) as client:
            for attempt in range(1, self._max_retries + 1):
                try:
                    response = await client.post(
                        f"{self._base_url}/embeddings",
                        headers={
                            "Authorization": f"Bearer {self._api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self._model,
                            "task": "retrieval.passage",
                            "dimensions": self._dimensions,
                            "input": texts,
                        },
                    )
                    if response.status_code in {429, 500, 502, 503, 504}:
                        raise _RetryableStatus(
                            response.status_code, _retry_after(response)
                        )
                    response.raise_for_status()
                    payload = response.json()
                    vectors = [
                        item["embedding"] for item in payload.get("data", [])
                    ]
                    if len(vectors) != len(texts):
                        raise EmbeddingProviderError(
                            "Jina returned an unexpected number of embeddings"
                        )
                    for vector in vectors:
                        if len(vector) != self._dimensions or not all(
                            math.isfinite(value) for value in vector
                        ):
                            raise EmbeddingProviderError(
                                "Jina returned an invalid embedding vector"
                            )
                    return vectors
                except _RetryableStatus as exc:
                    last_error = exc
                    if attempt >= self._max_retries:
                        break
                    delay = (
                        exc.retry_after
                        if exc.retry_after is not None
                        else _backoff(attempt)
                    )
                    logger.warning(
                        "Jina returned %s; retrying in %.1fs (%s/%s)",
                        exc.status_code,
                        delay,
                        attempt,
                        self._max_retries,
                    )
                    await asyncio.sleep(delay)
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    last_error = exc
                    if attempt >= self._max_retries:
                        break
                    delay = _backoff(attempt)
                    logger.warning(
                        "Jina request failed; retrying in %.1fs (%s/%s)",
                        delay,
                        attempt,
                        self._max_retries,
                    )
                    await asyncio.sleep(delay)
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code < 500:
                        raise EmbeddingProviderError(
                            f"Jina rejected the request with "
                            f"{exc.response.status_code}"
                        ) from exc
                    last_error = exc
                    if attempt >= self._max_retries:
                        break
                    await asyncio.sleep(_backoff(attempt))
        raise EmbeddingProviderError("Jina embedding request failed") from last_error


class _RetryableStatus(Exception):
    def __init__(self, status_code: int, retry_after: float | None) -> None:
        self.status_code = status_code
        self.retry_after = retry_after


def _retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(float(value), 0.0)
    except ValueError:
        return None


def _backoff(attempt: int) -> float:
    base = min(60.0, 2.0 * (2 ** (attempt - 1)))
    return base + random.uniform(0.0, min(1.0, base * 0.25))


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class _RateLimiter:
    def __init__(self, *, rpm: int, tpm: int) -> None:
        self._rpm = max(rpm, 1)
        self._tpm = max(tpm, 1)
        self._events: deque[tuple[float, int]] = deque()

    async def wait(self, *, tokens: int) -> None:
        while True:
            now = time.monotonic()
            while self._events and now - self._events[0][0] >= 60:
                self._events.popleft()
            used_tokens = sum(event[1] for event in self._events)
            if (
                len(self._events) < self._rpm
                and used_tokens + tokens <= self._tpm
            ):
                self._events.append((now, tokens))
                return
            wait_for = 60 - (now - self._events[0][0]) if self._events else 1.0
            await asyncio.sleep(min(max(wait_for, 0.1), 5.0))
