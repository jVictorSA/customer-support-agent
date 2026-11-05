import logging
import time
from typing import Any

from app.modules.agent.domain.chat import ChatCompletion
from app.modules.agent.application.trace import TraceRepository
from app.modules.agent.domain.trace import TraceStep

logger = logging.getLogger(__name__)


class AgentTraceRecorder:
    """Best-effort recorder for every agent and tool step."""

    def __init__(self, repository: TraceRepository, run_id: int) -> None:
        self._repository = repository
        self._run_id = run_id
        self._index = 0
        self.input_tokens = 0
        self.output_tokens = 0

    async def llm_step(
        self,
        *,
        agent_name: str,
        model: str,
        messages: list[dict[str, Any]],
        completion: ChatCompletion,
        temperature: float,
        max_tokens: int,
        latency_ms: int,
    ) -> None:
        await self._append(
            TraceStep(
                step_index=self._next(),
                agent_name=agent_name,
                step_type="llm_call",
                input={"messages": messages},
                output={
                    "content": completion.content,
                    "tool_calls": [
                        {"id": call.id, "name": call.name, "arguments": call.arguments}
                        for call in completion.tool_calls
                    ],
                },
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                prompt_tokens=completion.input_tokens,
                completion_tokens=completion.output_tokens,
                latency_ms=latency_ms,
                provider_request_id=str(completion.raw.get("id") or "") or None,
            )
        )

    async def tool_step(
        self,
        *,
        agent_name: str,
        tool_name: str,
        arguments: dict[str, Any],
        output: dict[str, Any],
        latency_ms: int,
        error_code: str | None = None,
    ) -> None:
        await self._append(
            TraceStep(
                step_index=self._next(),
                agent_name=agent_name,
                step_type="tool_call",
                tool_name=tool_name,
                input=arguments,
                output=output,
                latency_ms=latency_ms,
                error_code=error_code,
            )
        )

    async def validation_step(
        self,
        *,
        output: dict[str, Any],
        error_code: str | None = None,
    ) -> None:
        await self._append(
            TraceStep(
                step_index=self._next(),
                agent_name="grounding_validator",
                step_type="validation",
                output=output,
                error_code=error_code,
            )
        )

    def _next(self) -> int:
        value = self._index
        self._index += 1
        return value

    async def _append(self, step: TraceStep) -> None:
        self.input_tokens += step.prompt_tokens
        self.output_tokens += step.completion_tokens
        try:
            await self._repository.append_step(self._run_id, step)
        except Exception:
            logger.exception(
                "Could not persist agent trace step %s for run %s",
                step.step_index,
                self._run_id,
            )


def elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
