import logging
import time
from dataclasses import replace
from typing import Any

from app.modules.agent.application.agents import QueryRewriter
from app.modules.agent.application.interfaces import (
    CatalogGateway,
    ComplaintGateway,
    KnowledgeRetriever,
    OrderGateway,
)
from app.modules.agent.domain.context import HistoryMessage
from app.modules.agent.domain.settings import AgentRuntimeSettings
from app.modules.agent.domain.scope import CustomerScope
from app.modules.agent.application.trace_recorder import (
    AgentTraceRecorder,
    elapsed_ms,
)
from app.modules.agent.domain.intent import Intent
from app.modules.agent.domain.results import (
    Citation,
    CatalogItem,
    OrderSummary,
    ToolResult,
)

logger = logging.getLogger(__name__)


def tool_definitions(*, text_to_sql_enabled: bool) -> list[dict[str, Any]]:
    definitions = [
        _function(
            "search_store_knowledge",
            "Busca políticas, regras, horários, endereço, pagamento, frete, "
            "trocas, devoluções, garantia e promoções na base de documentos.",
            {
                "query": {
                    "type": "string",
                    "description": "Pergunta ou termos de busca.",
                }
            },
            ["query"],
        ),
        _function(
            "search_catalog",
            "Busca instrumentos no catálogo com filtros opcionais.",
            {
                "query": {"type": "string"},
                "category": {"type": "string"},
                "min_price": {"type": "number"},
                "max_price": {"type": "number"},
                "only_in_stock": {"type": "boolean"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10},
            },
            [],
        ),
        _function(
            "get_product_details",
            "Retorna detalhes, preço, estoque e promoções de um instrumento.",
            {"product_reference": {"type": "string"}},
            ["product_reference"],
        ),
        _function(
            "list_my_orders",
            "Lista os pedidos do cliente autenticado.",
            {
                "status": {
                    "type": "string",
                    "enum": [
                        "cancelled",
                        "confirmed",
                        "delivered",
                        "pending",
                        "shipped",
                    ],
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            [],
        ),
        _function(
            "get_order_status",
            "Consulta status/rastreamento de um pedido do cliente autenticado.",
            {
                "order_reference": {"type": "string"},
                "tracking_code": {"type": "string"},
            },
            [],
        ),
        _function(
            "register_complaint",
            "Registra uma reclamação do cliente e encaminha para atendimento humano.",
            {
                "category": {
                    "type": "string",
                    "enum": [
                        "order",
                        "product_defect",
                        "delivery",
                        "service",
                        "other",
                    ],
                },
                "description": {"type": "string"},
                "order_reference": {"type": "string"},
                "priority": {
                    "type": "string",
                    "enum": ["low", "normal", "high"],
                },
            },
            ["category", "description"],
        ),
    ]
    if text_to_sql_enabled:
        definitions.append(
            _function(
                "text_to_sql",
                "Consulta dados operacionais via SQL (temporariamente desabilitado).",
                {"question": {"type": "string"}},
                ["question"],
            )
        )
    return definitions


class StoreToolExecutor:
    def __init__(
        self,
        *,
        rewriter: QueryRewriter,
        retriever: KnowledgeRetriever,
        catalog: CatalogGateway,
        orders: OrderGateway,
        complaints: ComplaintGateway,
        trace: AgentTraceRecorder,
        settings: AgentRuntimeSettings,
    ) -> None:
        self._rewriter = rewriter
        self._retriever = retriever
        self._catalog = catalog
        self._orders = orders
        self._complaints = complaints
        self._trace = trace
        self._settings = settings

    @property
    def definitions(self) -> list[dict[str, Any]]:
        return tool_definitions(
            text_to_sql_enabled=self._settings.text_to_sql_enabled
        )

    async def execute(
        self,
        *,
        name: str,
        arguments: dict[str, Any],
        scope: CustomerScope,
        history: list[HistoryMessage],
        intent: Intent,
    ) -> ToolResult:
        started = time.monotonic()
        try:
            result = await self._dispatch(
                name=name,
                arguments=arguments,
                scope=scope,
                history=history,
                intent=intent,
            )
        except Exception:
            logger.exception("Tool %s failed", name)
            result = ToolResult(
                ok=False,
                error_code="tool_execution_failed",
                error_message="Não foi possível concluir essa consulta agora.",
            )
        if not result.tool_name:
            result = replace(result, tool_name=name)
        await self._trace.tool_step(
            agent_name="orchestrator",
            tool_name=name,
            arguments=arguments,
            output=result.to_payload(),
            latency_ms=elapsed_ms(started),
            error_code=result.error_code,
        )
        return result

    async def _dispatch(
        self,
        *,
        name: str,
        arguments: dict[str, Any],
        scope: CustomerScope,
        history: list[HistoryMessage],
        intent: Intent,
    ) -> ToolResult:
        if name == "search_store_knowledge":
            query = str(arguments.get("query") or "").strip()
            if not query:
                return _error("invalid_arguments", "query is required")
            rewritten = await self._rewriter.rewrite(
                query=query, history=history, intent=intent
            )
            passages = await self._retriever.search(rewritten)
            return ToolResult(
                ok=True,
                data=[
                    {
                        "reference": passage.reference,
                        "title": passage.title,
                        "path": passage.path,
                        "document": passage.document_name,
                        "content": passage.content,
                    }
                    for passage in passages
                ],
                citations=tuple(
                    Citation("knowledge", passage.reference)
                    for passage in passages
                ),
            )

        if name == "search_catalog":
            items = await self._catalog.search_catalog(
                query=_optional_str(arguments.get("query")),
                category=_optional_str(arguments.get("category")),
                min_price=_optional_float(arguments.get("min_price")),
                max_price=_optional_float(arguments.get("max_price")),
                only_in_stock=bool(arguments.get("only_in_stock", False)),
                limit=_limit(arguments.get("limit"), default=5),
            )
            return ToolResult(
                ok=True,
                data=[_catalog_payload(item) for item in items],
                citations=tuple(
                    Citation("product", f"product:{item.product_id}")
                    for item in items
                ),
            )

        if name == "get_product_details":
            reference = str(
                arguments.get("product_reference") or ""
            ).strip()
            if not reference:
                return _error(
                    "invalid_arguments", "product_reference is required"
                )
            item = await self._catalog.get_product(reference)
            if item is None:
                return ToolResult(ok=True, data=None)
            return ToolResult(
                ok=True,
                data=_catalog_payload(item),
                citations=(Citation("product", f"product:{item.product_id}"),),
            )

        if name == "list_my_orders":
            orders = await self._orders.list_orders(
                customer_id=scope.customer_id,
                status=_optional_str(arguments.get("status")),
                limit=_limit(arguments.get("limit"), default=10),
            )
            return ToolResult(
                ok=True,
                data=[_order_payload(order) for order in orders],
                citations=tuple(
                    Citation("order", f"order:{order.order_id}")
                    for order in orders
                ),
            )

        if name == "get_order_status":
            reference = _optional_str(arguments.get("order_reference"))
            tracking = _optional_str(arguments.get("tracking_code"))
            if not reference and not tracking:
                return _error(
                    "invalid_arguments",
                    "order_reference or tracking_code is required",
                )
            order = (
                await self._orders.get_order(
                    customer_id=scope.customer_id, reference=reference
                )
                if reference
                else await self._orders.get_order_by_tracking(
                    customer_id=scope.customer_id, tracking_code=tracking or ""
                )
            )
            if order is None:
                return ToolResult(ok=True, data=None)
            return ToolResult(
                ok=True,
                data=_order_payload(order),
                citations=(Citation("order", f"order:{order.order_id}"),),
            )

        if name == "register_complaint":
            category = str(arguments.get("category") or "other")
            description = str(arguments.get("description") or "").strip()
            if not description:
                return _error(
                    "invalid_arguments", "description is required"
                )
            complaint = await self._complaints.register(
                conversation_id=scope.conversation_id,
                customer_id=scope.customer_id,
                message_id=scope.message_id,
                category=category,
                description=description,
                order_reference=_optional_str(
                    arguments.get("order_reference")
                ),
                priority=str(arguments.get("priority") or "normal"),
            )
            return ToolResult(
                ok=True,
                data={
                    "protocol": complaint.public_id,
                    "status": complaint.status,
                    "category": complaint.category,
                    "already_open": complaint.already_open,
                    "return_window": "até 24 horas úteis",
                },
                citations=(
                    Citation(
                        "complaint", f"complaint:{complaint.public_id}"
                    ),
                ),
            )

        if name == "text_to_sql":
            return ToolResult(
                ok=False,
                error_code="not_implemented",
                error_message=(
                    "A consulta SQL ainda não está disponível. Use as "
                    "ferramentas estruturadas de catálogo e pedidos."
                ),
            )

        return _error("unknown_tool", f"Unknown tool: {name}")


def _function(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str],
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _limit(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(parsed, 20))


def _error(code: str, message: str) -> ToolResult:
    return ToolResult(ok=False, error_code=code, error_message=message)


def _catalog_payload(item: CatalogItem) -> dict[str, Any]:
    return {
        "product_id": item.product_id,
        "name": item.name,
        "category": item.category,
        "price_brl": item.price_brl,
        "effective_price_brl": item.effective_price_brl,
        "stock_quantity": item.stock_quantity,
        "status": item.status,
        "description": item.description,
        "promotions": [
            {
                "promotion_id": promotion.promotion_id,
                "discount_percent": promotion.discount_percent,
                "description": promotion.description,
            }
            for promotion in item.promotions
        ],
        "specs": item.specs,
    }


def _order_payload(order: OrderSummary) -> dict[str, Any]:
    return {
        "order_id": order.order_id,
        "status": order.status,
        "total_brl": order.total_brl,
        "payment_method": order.payment_method,
        "order_date": order.order_date,
        "tracking_code": order.tracking_code,
        "estimated_delivery": order.estimated_delivery,
        "items": [
            {
                "product_id": item.product_id,
                "product_name": item.product_name,
                "quantity": item.quantity,
            }
            for item in order.items
        ],
    }
