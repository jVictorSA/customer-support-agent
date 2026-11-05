from datetime import UTC, datetime
import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agent.domain.trace import TraceStep
from app.modules.agent.infrastructure.trace.models import (
    AgentRunModel,
    AgentRunStatus,
    AgentStepModel,
    AgentStepType,
)


class SqlAlchemyTraceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def start_run(
        self,
        *,
        conversation_id: int,
        customer_id: int,
        user_message_id: int,
        intent: str | None,
        prompt_version: str,
        model: str,
    ) -> int:
        async with self._session.begin():
            run = AgentRunModel(
                conversation_id=conversation_id,
                customer_id=customer_id,
                user_message_id=user_message_id,
                intent=intent,
                prompt_version=prompt_version,
                model=model,
                status=AgentRunStatus.RUNNING,
                started_at=datetime.now(UTC),
            )
            self._session.add(run)
            await self._session.flush()
            return run.run_id

    async def append_step(self, run_id: int, step: TraceStep) -> None:
        async with self._session.begin():
            self._session.add(
                AgentStepModel(
                    run_id=run_id,
                    step_index=step.step_index,
                    agent_name=step.agent_name,
                    step_type=AgentStepType(step.step_type),
                    tool_name=step.tool_name,
                    input_data=_json_safe(step.input),
                    output_data=_json_safe(step.output),
                    model=step.model,
                    temperature=step.temperature,
                    max_tokens=step.max_tokens,
                    prompt_tokens=step.prompt_tokens,
                    completion_tokens=step.completion_tokens,
                    latency_ms=step.latency_ms,
                    provider_request_id=step.provider_request_id,
                    error_code=step.error_code,
                )
            )
            await self._session.flush()

    async def set_run_intent(self, run_id: int, intent: str) -> None:
        async with self._session.begin():
            run = await self._session.get(AgentRunModel, run_id)
            if run is None:
                return
            run.intent = intent
            await self._session.flush()

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
    ) -> None:
        async with self._session.begin():
            run = await self._session.get(AgentRunModel, run_id)
            if run is None:
                return
            finished = datetime.now(UTC)
            run.status = AgentRunStatus(status)
            run.finished_at = finished
            run.latency_ms = int(
                (finished - run.started_at).total_seconds() * 1000
            )
            run.input_tokens = input_tokens
            run.output_tokens = output_tokens
            run.fallback_used = fallback_used
            run.error_code = error_code
            if assistant_message_id is not None:
                run.assistant_message_id = assistant_message_id
            await self._session.flush()


def _json_safe(value: Any) -> Any:
    """Normalize trace payloads so arbitrary tool objects never break a run."""
    return json.loads(json.dumps(value, default=str, ensure_ascii=False))
