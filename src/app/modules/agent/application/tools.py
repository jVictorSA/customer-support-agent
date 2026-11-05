import logging
import time
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from app.modules.agent.application.agents import QueryRewriter
from app.modules.agent.application.interfaces import (
    CatalogGateway,
    Clock,
    ComplaintGateway,
    KnowledgeRetriever,
    OrderGateway,
    TextToSqlGateway,
)
from app.modules.agent.domain.context import HistoryMessage
from app.modules.agent.domain.settings import AgentRuntimeSettings
from app.modules.agent.domain.scope import CustomerScope
from app.modules.agent.application.trace_recorder import (
    AgentTraceRecorder,
    elapsed_ms,
)
from app.modules.agent.domain.intent import Intent
from app.modules.agent.domain.store_policy import (
    ReturnItemContext,
    ReturnOrderContext,
    ReturnReason,
    StoreSchedule,
    calculate_payment_options,
    estimate_shipping,
    evaluate_return,
)
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
            "get_store_status",
            "Retorna se a loja está aberta agora, o horário de hoje e o "
            "próximo horário de atendimento.",
            {},
            [],
        ),
        _function(
            "check_return_eligibility",
            "Verifica se um item do pedido do cliente pode ser devolvido ou "
            "trocado segundo as políticas da loja.",
            {
                "order_reference": {"type": "string"},
                "product_reference": {"type": "string"},
                "reason": {
                    "type": "string",
                    "enum": ["withdrawal", "defect", "preference"],
                },
                "desired_product_reference": {"type": "string"},
            },
            ["order_reference", "product_reference", "reason"],
        ),
        _function(
            "calculate_payment_options",
            "Calcula PIX, débito, boleto e parcelas de cartão para um produto "
            "ou pedido, aplicando os mínimos e descontos da loja.",
            {
                "product_reference": {"type": "string"},
                "order_reference": {"type": "string"},
            },
            [],
        ),
        _function(
            "estimate_shipping",
            "Estima o frete e o prazo para um CEP com base na política da loja.",
            {
                "cep": {"type": "string"},
                "product_reference": {"type": "string"},
                "order_reference": {"type": "string"},
            },
            ["cep"],
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
                "Responde perguntas analíticas e consultas complexas sobre "
                "catálogo, estoque, promoções e os pedidos do próprio cliente. "
                "Use para contagens, somas, médias, rankings, comparações e "
                "buscas por características técnicas ou marca.",
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
        text_to_sql: TextToSqlGateway | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._rewriter = rewriter
        self._retriever = retriever
        self._catalog = catalog
        self._orders = orders
        self._complaints = complaints
        self._trace = trace
        self._settings = settings
        self._text_to_sql = text_to_sql
        self._clock = clock

    @property
    def definitions(self) -> list[dict[str, Any]]:
        return tool_definitions(
            text_to_sql_enabled=(
                self._settings.text_to_sql_enabled
                and self._text_to_sql is not None
            )
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
            output=result.trace_payload or result.to_payload(),
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

        if name == "get_store_status":
            return ToolResult(ok=True, data=self._store_status_payload())

        if name == "check_return_eligibility":
            reference = _optional_str(arguments.get("order_reference"))
            product_reference = _optional_str(
                arguments.get("product_reference")
            )
            reason_value = _optional_str(arguments.get("reason"))
            if not reference or not product_reference or not reason_value:
                return _error(
                    "invalid_arguments",
                    "order_reference, product_reference and reason are required",
                )
            try:
                reason = ReturnReason(reason_value)
            except ValueError:
                return _error("invalid_arguments", "invalid return reason")
            order = await self._orders.get_order(
                customer_id=scope.customer_id, reference=reference
            )
            if order is None:
                return ToolResult(ok=True, data=None)
            product_id = _match_product_id(order, product_reference)
            if product_id is None:
                return _error(
                    "product_not_in_order",
                    "Produto não encontrado no pedido informado.",
                )
            desired_stock: bool | None = None
            desired_reference = _optional_str(
                arguments.get("desired_product_reference")
            )
            if desired_reference:
                desired = await self._catalog.get_product(desired_reference)
                desired_stock = (
                    desired.stock_quantity > 0
                    if desired is not None
                    else False
                )
            eligibility = evaluate_return(
                order=_return_order_context(order),
                product_id=product_id,
                reason=reason,
                today=self._today(),
                desired_product_in_stock=desired_stock,
            )
            return ToolResult(
                ok=True,
                data=_return_payload(eligibility),
                citations=(Citation("order", f"order:{order.order_id}"),),
            )

        if name == "calculate_payment_options":
            priced = await self._resolve_amount(arguments, scope)
            if priced is None:
                return _error(
                    "invalid_arguments",
                    "Informe product_reference ou order_reference.",
                )
            amount, promotional, source = priced
            payment = calculate_payment_options(
                amount, promotional=promotional
            )
            return ToolResult(
                ok=True,
                data={
                    "source": source,
                    "amount_brl": float(payment.amount_brl),
                    "promotional": payment.promotional,
                    "combined_allowed": payment.combined_allowed,
                    "options": [
                        {
                            "method": option.method,
                            "label": option.label,
                            "total_brl": float(option.total_brl),
                            "installments": option.installments,
                            "installment_brl": (
                                float(option.installment_brl)
                                if option.installment_brl is not None
                                else None
                            ),
                            "discount_percent": option.discount_percent,
                            "available": option.available,
                            "note": option.note,
                        }
                        for option in payment.options
                    ],
                },
                citations=(Citation("product", source),)
                if source.startswith("product:")
                else (),
            )

        if name == "estimate_shipping":
            cep = _optional_str(arguments.get("cep"))
            if not cep:
                return _error("invalid_arguments", "cep is required")
            priced = await self._resolve_amount(arguments, scope)
            if priced is None:
                return _error(
                    "invalid_arguments",
                    "Informe product_reference ou order_reference.",
                )
            amount, _, source = priced
            has_large_items = await self._has_large_items(
                arguments, scope
            )
            try:
                quote = estimate_shipping(
                    cep=cep,
                    subtotal_brl=amount,
                    metro_cep_prefixes=self._settings.store_metro_cep_prefixes,
                    has_large_items=has_large_items,
                )
            except ValueError as exc:
                return _error("invalid_arguments", str(exc))
            return ToolResult(
                ok=True,
                data={
                    "source": source,
                    "cep": quote.cep,
                    "zone": quote.zone.value,
                    "subtotal_brl": float(quote.subtotal_brl),
                    "shipping_brl": (
                        float(quote.shipping_brl)
                        if quote.shipping_brl is not None
                        else None
                    ),
                    "free_shipping": quote.free_shipping,
                    "deadline": quote.deadline,
                    "requires_quote": quote.requires_quote,
                    "modalities": list(quote.modalities),
                    "note": quote.note,
                },
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
            if self._text_to_sql is None:
                return ToolResult(
                    ok=False,
                    error_code="text_to_sql_unavailable",
                    error_message=(
                        "A consulta SQL não está disponível neste ambiente. "
                        "Use as ferramentas estruturadas de catálogo e pedidos."
                    ),
                )
            question = str(arguments.get("question") or "").strip()
            if not question:
                return _error("invalid_arguments", "question is required")
            return await self._text_to_sql.answer(
                question=question,
                history=history,
                scope=scope,
            )

        return _error("unknown_tool", f"Unknown tool: {name}")

    def _now(self) -> datetime:
        return self._clock.now() if self._clock is not None else datetime.now(UTC)

    def _today(self) -> date:
        return self._now().astimezone(
            ZoneInfo(self._settings.store_timezone)
        ).date()

    def _store_status_payload(self) -> dict[str, Any]:
        schedule = StoreSchedule(
            timezone=self._settings.store_timezone,
            holidays=frozenset(
                date.fromisoformat(value)
                for value in self._settings.store_holidays
            ),
        )
        status = schedule.status_at(self._now())
        return {
            "is_open": status.is_open,
            "local_time": status.local_time.isoformat(),
            "today_open": (
                status.today_open.isoformat() if status.today_open else None
            ),
            "today_close": (
                status.today_close.isoformat() if status.today_close else None
            ),
            "next_opening": (
                status.next_opening.isoformat()
                if status.next_opening
                else None
            ),
            "is_holiday": status.is_holiday,
        }

    async def _resolve_amount(
        self, arguments: dict[str, Any], scope: CustomerScope
    ) -> tuple[Decimal, bool, str] | None:
        product_reference = _optional_str(arguments.get("product_reference"))
        if product_reference:
            product = await self._catalog.get_product(product_reference)
            if product is None:
                return None
            promotional = bool(product.promotions)
            amount = (
                Decimal(str(product.effective_price_brl))
                if promotional
                else Decimal(str(product.price_brl))
            )
            return amount, promotional, f"product:{product.product_id}"

        order_reference = _optional_str(arguments.get("order_reference"))
        if order_reference:
            order = await self._orders.get_order(
                customer_id=scope.customer_id, reference=order_reference
            )
            if order is None:
                return None
            return (
                Decimal(str(order.total_brl)),
                False,
                f"order:{order.order_id}",
            )
        return None

    async def _has_large_items(
        self, arguments: dict[str, Any], scope: CustomerScope
    ) -> bool:
        product_reference = _optional_str(arguments.get("product_reference"))
        if product_reference:
            product = await self._catalog.get_product(product_reference)
            return product is not None and _is_large_item(
                product.category, product.name
            )
        order_reference = _optional_str(arguments.get("order_reference"))
        if order_reference:
            order = await self._orders.get_order(
                customer_id=scope.customer_id, reference=order_reference
            )
            return order is not None and any(
                _is_large_item(None, item.product_name or "")
                for item in order.items
            )
        return False


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


def _match_product_id(order: OrderSummary, reference: str) -> int | None:
    try:
        product_id = int(reference)
    except ValueError:
        product_id = None
    if product_id is not None:
        return product_id if any(
            item.product_id == product_id for item in order.items
        ) else None
    lowered = reference.lower()
    for item in order.items:
        if lowered in (item.product_name or "").lower():
            return item.product_id
    return None


def _return_order_context(order: OrderSummary) -> ReturnOrderContext:
    return ReturnOrderContext(
        order_id=order.order_id,
        status=order.status,
        sales_channel=order.sales_channel,
        order_date=_parse_date(order.order_date),
        delivered_at=(
            _parse_date(order.delivered_at)
            if order.delivered_at is not None
            else None
        ),
        items=tuple(
            ReturnItemContext(
                product_id=item.product_id,
                product_name=item.product_name,
                is_final_sale=item.is_final_sale,
                is_customized=item.is_customized,
                is_hygiene_restricted=item.is_hygiene_restricted,
            )
            for item in order.items
        ),
    )


def _parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def _return_payload(eligibility) -> dict[str, Any]:
    return {
        "eligible": eligibility.eligible,
        "reason": eligibility.reason,
        "rule": eligibility.rule,
        "deadline": (
            eligibility.deadline.isoformat()
            if eligibility.deadline is not None
            else None
        ),
        "days_remaining": eligibility.days_remaining,
        "requirements": list(eligibility.requirements),
        "next_step": eligibility.next_step,
        "handoff_required": eligibility.handoff_required,
    }


def _is_large_item(category: str | None, name: str) -> bool:
    if category in {"Baterias e Percussão", "Teclados e Pianos"}:
        return True
    lowered = name.lower()
    return any(
        keyword in lowered
        for keyword in ("bateria", "piano", "contrabaixo", "teclado")
    )


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
                "starts_at": promotion.starts_at,
                "ends_at": promotion.ends_at,
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
        "sales_channel": order.sales_channel,
        "tracking_code": order.tracking_code,
        "estimated_delivery": order.estimated_delivery,
        "delivered_at": order.delivered_at,
        "items": [
            {
                "product_id": item.product_id,
                "product_name": item.product_name,
                "quantity": item.quantity,
                "is_final_sale": item.is_final_sale,
                "is_customized": item.is_customized,
                "is_hygiene_restricted": item.is_hygiene_restricted,
            }
            for item in order.items
        ],
    }
