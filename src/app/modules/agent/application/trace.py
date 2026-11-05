from typing import Protocol

from app.modules.agent.domain.trace import TraceStep


class TraceRepository(Protocol):
    async def start_run(
        self,
        *,
        conversation_id: int,
        customer_id: int,
        user_message_id: int,
        intent: str | None,
        prompt_version: str,
        model: str,
    ) -> int: ...

    async def append_step(self, run_id: int, step: TraceStep) -> None: ...

    async def set_run_intent(self, run_id: int, intent: str) -> None: ...

    async def finish_run(
        self,
        run_id: int,
        *,
        status: str,
        input_tokens: int,
        output_tokens: int,
        fallback_used: bool,
        error_code: str | None,
        assistant_message_id: int | None = None,
    ) -> None: ...
