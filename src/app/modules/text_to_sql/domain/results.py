from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TextToSqlStatus(StrEnum):
    ANSWERED = "answered"
    CLARIFICATION_REQUIRED = "clarification_required"
    UNSUPPORTED = "unsupported"
    UNAVAILABLE = "unavailable"


class SqlGenerationStatus(StrEnum):
    METRIC = "metric"
    SQL = "sql"
    CLARIFICATION_REQUIRED = "clarification_required"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class TextToSqlHistoryItem:
    role: str
    content: str


@dataclass(frozen=True, slots=True)
class TextToSqlRequest:
    question: str
    customer_id: int
    history: tuple[TextToSqlHistoryItem, ...] = ()


@dataclass(frozen=True, slots=True)
class SqlGeneration:
    status: SqlGenerationStatus
    sql: str | None = None
    metric_id: str | None = None
    explanation: str = ""
    tables_used: tuple[str, ...] = ()
    columns_used: tuple[str, ...] = ()
    clarification_question: str | None = None


@dataclass(frozen=True, slots=True)
class SqlValidationIssue:
    code: str
    message: str
    repairable: bool = True


@dataclass(frozen=True, slots=True)
class SqlValidationResult:
    ok: bool
    normalized_sql: str | None
    issues: tuple[SqlValidationIssue, ...] = ()
    tables_used: tuple[str, ...] = ()
    columns_used: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SqlQueryResult:
    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    row_count: int
    truncated: bool = False


@dataclass(frozen=True, slots=True)
class TextToSqlOutcome:
    status: TextToSqlStatus
    metric_id: str | None = None
    columns: tuple[str, ...] = ()
    rows: tuple[dict[str, Any], ...] = ()
    row_count: int = 0
    truncated: bool = False
    summary: str = ""
    question: str | None = None
    message: str | None = None
    sql: str | None = None
    query_hash: str | None = None
    attempts: int = 0
    error_code: str | None = None
    trace_output: dict[str, Any] = field(default_factory=dict)


class SqlExecutionFailure(Exception):
    """A sanitized database execution failure raised by infrastructure."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)
