from types import SimpleNamespace

import pytest

openai = pytest.importorskip("openai")

from app.modules.documents.infrastructure.summarization.deepseek_summarizer import (  # noqa: E402
    DeepSeekSectionSummarizer,
)


class FakeCompletions:
    def __init__(self) -> None:
        self.max_tokens: list[int] = []
        self.extra_bodies: list[object] = []

    async def create(self, **kwargs):
        self.max_tokens.append(kwargs["max_tokens"])
        self.extra_bodies.append(kwargs.get("extra_body"))
        if len(self.max_tokens) == 1:
            return _response("", finish_reason="length", completion_tokens=300)
        return _response("Resumo final", finish_reason="stop", completion_tokens=80)


class FakeClient:
    last: "FakeClient"

    def __init__(self, **kwargs) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions())
        FakeClient.last = self


def _response(content: str, *, finish_reason: str, completion_tokens: int):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
                finish_reason=finish_reason,
            )
        ],
        usage=SimpleNamespace(
            completion_tokens=completion_tokens,
            completion_tokens_details=SimpleNamespace(reasoning_tokens=250),
        ),
    )


async def test_retries_with_larger_budget_when_reasoning_consumes_output(
    monkeypatch,
) -> None:
    monkeypatch.setattr(openai, "AsyncOpenAI", FakeClient)
    summarizer = DeepSeekSectionSummarizer(
        api_key="key",
        base_url="https://example.test",
        model="deepseek-flash",
        version="v1",
        timeout=10,
        max_retries=0,
        max_tokens=300,
    )

    summary = await summarizer.summarize(
        document_title="Manual",
        section_path="Introdução",
        direct_content="Conteúdo",
        child_summaries=[],
    )

    assert summary == "Resumo final"
    assert FakeClient.last.chat.completions.max_tokens == [300, 1200]
    assert FakeClient.last.chat.completions.extra_bodies == [
        {"thinking": {"type": "disabled"}},
        {"thinking": {"type": "disabled"}},
    ]
