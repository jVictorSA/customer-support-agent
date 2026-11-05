from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class TraceStep:
    step_index: int
    agent_name: str
    step_type: str
    tool_name: str | None = None
    input: dict[str, Any] = field(default_factory=dict)
    output: dict[str, Any] = field(default_factory=dict)
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    provider_request_id: str | None = None
    error_code: str | None = None
