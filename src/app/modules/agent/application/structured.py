import json
import re
from typing import Any

from app.modules.agent.domain.intent import Intent, IntentKind
from app.modules.agent.domain.results import Citation, WriterAnswer

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


def coerce_intent(data: dict[str, Any]) -> Intent:
    raw = str(data.get("primary_intent", "ambiguous"))
    try:
        primary = IntentKind(raw)
    except ValueError:
        primary = IntentKind.AMBIGUOUS

    secondary: list[IntentKind] = []
    for item in data.get("secondary_intents") or []:
        try:
            secondary.append(IntentKind(str(item)))
        except ValueError:
            continue

    entities = data.get("entities")
    if not isinstance(entities, dict):
        entities = {}

    missing = data.get("missing_information")
    if not isinstance(missing, list):
        missing = []

    out_of_scope = bool(data.get("out_of_scope"))
    out_of_scope_type = str(data.get("out_of_scope_type") or "none")
    if out_of_scope_type not in {
        "none",
        "accessory",
        "benign_off_topic",
        "harmful_or_illegal",
        "other",
    }:
        out_of_scope_type = "other" if out_of_scope else "none"
    if out_of_scope and out_of_scope_type == "none":
        out_of_scope_type = "other"

    return Intent(
        primary_intent=primary,
        secondary_intents=tuple(secondary),
        entities=entities,
        needs_knowledge=bool(data.get("needs_knowledge")),
        needs_operational_data=bool(data.get("needs_operational_data")),
        wants_complaint=bool(data.get("wants_complaint")),
        out_of_scope=out_of_scope,
        out_of_scope_type=out_of_scope_type,
        urgency=str(data.get("urgency") or "normal"),
        missing_information=tuple(str(item) for item in missing),
    )


def coerce_rewriter(data: dict[str, Any]) -> str:
    query = str(data.get("standalone_query") or "").strip()
    if not query:
        raise ValueError("standalone_query is required")
    return query


def coerce_writer(data: dict[str, Any]) -> WriterAnswer:
    message = str(data.get("message") or "").strip()
    if not message:
        raise ValueError("message is required")

    citations: list[Citation] = []
    for item in data.get("citations") or []:
        if not isinstance(item, dict):
            continue
        reference = str(item.get("reference") or "").strip()
        if not reference:
            continue
        citations.append(
            Citation(
                source_type=str(item.get("source_type") or "knowledge"),
                reference=reference,
            )
        )

    follow_up = data.get("follow_up_question")
    return WriterAnswer(
        message=message,
        citations=tuple(citations),
        needs_human_handoff=bool(data.get("needs_human_handoff")),
        follow_up_question=str(follow_up) if follow_up else None,
        confidence=str(data.get("confidence") or "medium"),
    )
