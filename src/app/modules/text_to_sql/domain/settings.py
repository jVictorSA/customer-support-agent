from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TextToSqlSettings:
    model: str
    temperature: float = 0.0
    max_tokens: int = 900
    max_attempts: int = 2
    max_rows: int = 50
    writer_rows: int = 20
    statement_timeout_ms: int = 5000
    max_joins: int = 4
    max_ast_depth: int = 30
    max_ctes: int = 3
    max_union_branches: int = 2
    max_result_chars: int = 6000
