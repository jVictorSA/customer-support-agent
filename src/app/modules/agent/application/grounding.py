import re
from typing import Any

from app.modules.agent.domain.intent import Intent
from app.modules.agent.domain.results import (
    OrchestratorOutcome,
    ToolResult,
    WriterAnswer,
)

_CURRENCY = re.compile(r"R\$\s*([0-9][0-9\.]*(?:,[0-9]{2})?)")


class GroundingValidator:
    def validate(
        self,
        *,
        intent: Intent,
        outcome: OrchestratorOutcome,
        answer: WriterAnswer,
    ) -> list[str]:
        errors: list[str] = []
        allowed = {
            citation.reference
            for result in outcome.tool_results
            for citation in result.citations
        }

        for citation in answer.citations:
            if citation.reference not in allowed:
                errors.append(
                    f"citação inexistente: {citation.reference}"
                )

        if intent.needs_operational_data:
            has_data = any(
                result.ok
                and result.tool_name
                in {
                    "search_catalog",
                    "get_product_details",
                    "list_my_orders",
                    "get_order_status",
                }
                for result in outcome.tool_results
            )
            if not has_data:
                errors.append(
                    "a pergunta exige dado operacional, mas nenhuma consulta "
                    "de catálogo ou pedido foi concluída"
                )

        if intent.primary_intent.value == "policy":
            has_knowledge = any(
                result.ok
                and result.tool_name == "search_store_knowledge"
                for result in outcome.tool_results
            )
            if not has_knowledge:
                errors.append(
                    "a pergunta é de política, mas a base de conhecimento "
                    "não foi consultada"
                )

        numeric_values = _numbers_from_results(outcome.tool_results)
        for raw in _CURRENCY.findall(answer.message):
            value = _parse_brl(raw)
            if value is None:
                continue
            if not any(abs(value - candidate) < 0.01 for candidate in numeric_values):
                errors.append(
                    f"valor monetário não confirmado por ferramenta: R$ {raw}"
                )

        if not answer.message.strip():
            errors.append("mensagem vazia")
        return errors


def _numbers_from_results(results: tuple[ToolResult, ...]) -> list[float]:
    values: list[float] = []

    def walk(value: Any) -> None:
        if isinstance(value, bool):
            return
        if isinstance(value, (int, float)):
            values.append(float(value))
        elif isinstance(value, str):
            for match in _CURRENCY.findall(value):
                parsed = _parse_brl(match)
                if parsed is not None:
                    values.append(parsed)
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)

    for result in results:
        walk(result.data)
    return values


def _parse_brl(raw: str) -> float | None:
    value = raw.strip()
    if "," in value:
        normalized = value.replace(".", "").replace(",", ".")
    elif value.count(".") == 1 and len(value.split(".")[1]) <= 2:
        normalized = value
    else:
        normalized = value.replace(".", "")
    try:
        return float(normalized)
    except ValueError:
        return None
