import json
import re
from typing import Any

from app.modules.text_to_sql.domain.results import (
    SqlGeneration,
    SqlGenerationStatus,
)

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_json_object(text: str | None) -> dict[str, Any]:
    if not text:
        raise ValueError("empty completion")
    cleaned = _FENCE.sub("", text.strip()).strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("completion is not a JSON object") from exc
        value = json.loads(cleaned[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("completion is not a JSON object")
    return value


def coerce_rewriter(data: dict[str, Any]) -> str:
    query = str(data.get("standalone_question") or "").strip()
    if not query:
        raise ValueError("standalone_question is required")
    return query


def coerce_generation(data: dict[str, Any]) -> SqlGeneration:
    raw_status = str(data.get("status") or "").strip()
    try:
        status = SqlGenerationStatus(raw_status)
    except ValueError as exc:
        raise ValueError(f"unsupported generation status: {raw_status}") from exc

    metric_id = _optional_str(data.get("metric_id"))
    sql = _optional_str(data.get("sql"))
    question = _optional_str(data.get("clarification_question"))
    explanation = str(data.get("explanation") or "").strip()

    if status is SqlGenerationStatus.METRIC and not metric_id:
        raise ValueError("metric_id is required for metric status")
    if status is SqlGenerationStatus.SQL and not sql:
        raise ValueError("sql is required for sql status")
    if (
        status is SqlGenerationStatus.CLARIFICATION_REQUIRED
        and not question
    ):
        raise ValueError("clarification_question is required")

    return SqlGeneration(
        status=status,
        sql=sql,
        metric_id=metric_id,
        explanation=explanation,
        tables_used=_string_tuple(data.get("tables_used")),
        columns_used=_string_tuple(data.get("columns_used")),
        clarification_question=question,
    )


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())
