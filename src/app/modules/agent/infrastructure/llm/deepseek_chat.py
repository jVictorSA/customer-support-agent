import json
import logging
from typing import Any

from app.modules.agent.domain.chat import ChatCompletion, ChatToolCall

logger = logging.getLogger(__name__)


class AgentProviderError(Exception):
    pass


class DeepSeekChatClient:
    """OpenAI-compatible chat client used by every agent role."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        default_model: str,
        timeout: float,
        max_retries: int,
        disable_thinking: bool = True,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._default_model = default_model
        self._timeout = timeout
        self._max_retries = max_retries
        self._disable_thinking = disable_thinking
        self._client = None

    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1000,
        json_mode: bool = False,
        model: str | None = None,
    ) -> ChatCompletion:
        if not self._api_key:
            raise AgentProviderError("DEEPSEEK_API_KEY is not configured")
        from openai import AsyncOpenAI

        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._timeout,
                max_retries=self._max_retries,
            )
        client = self._client
        request: dict[str, Any] = {
            "model": model or self._default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            request["tools"] = tools
            request["tool_choice"] = "auto"
        if json_mode:
            request["response_format"] = {"type": "json_object"}
        if self._disable_thinking:
            request["extra_body"] = {"thinking": {"type": "disabled"}}

        try:
            response = await client.chat.completions.create(**request)
        except Exception as exc:
            logger.exception("DeepSeek chat completion failed")
            raise AgentProviderError("DeepSeek request failed") from exc

        choice = response.choices[0]
        message = choice.message
        calls: list[ChatToolCall] = []
        for call in message.tool_calls or []:
            try:
                arguments = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
            if not isinstance(arguments, dict):
                arguments = {}
            calls.append(
                ChatToolCall(
                    id=call.id,
                    name=call.function.name,
                    arguments=arguments,
                )
            )

        usage = response.usage
        return ChatCompletion(
            content=message.content,
            tool_calls=tuple(calls),
            input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            model=str(response.model or request["model"]),
            raw=response.model_dump(),
        )
