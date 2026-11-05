from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AgentRuntimeSettings:
    max_iterations: int = 6
    history_max_messages: int = 20
    history_max_tokens: int = 6000
    prompt_version: str = "conversation-v1"
    text_to_sql_enabled: bool = False
    disable_thinking: bool = True

    intent_model: str = ""
    orchestrator_model: str = ""
    rewriter_model: str = ""
    writer_model: str = ""

    intent_temperature: float = 0.0
    orchestrator_temperature: float = 0.1
    rewriter_temperature: float = 0.0
    writer_temperature: float = 0.4

    intent_max_tokens: int = 600
    orchestrator_max_tokens: int = 1200
    rewriter_max_tokens: int = 400
    writer_max_tokens: int = 1200
    tool_result_max_chars: int = 6000
    store_timezone: str = "America/Sao_Paulo"
    store_holidays: tuple[str, ...] = ()
    store_metro_cep_prefixes: tuple[str, ...] = ("790", "791")
