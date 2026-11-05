from typing import Any, Protocol

from app.modules.agent.domain.chat import ChatCompletion
from app.modules.agent.domain.context import (
    AppendedMessage,
    DeliveryTarget,
    HistoryMessage,
    ProcessingContext,
)
from app.modules.agent.domain.results import (
    CatalogItem,
    KnowledgePassage,
    OrderSummary,
    RegisteredComplaint,
)


class ChatModel(Protocol):
    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1000,
        json_mode: bool = False,
        model: str | None = None,
    ) -> ChatCompletion: ...


class TokenCounter(Protocol):
    def count(self, text: str) -> int: ...


class KnowledgeRetriever(Protocol):
    async def search(
        self, query: str, *, limit: int | None = None
    ) -> list[KnowledgePassage]: ...


class CatalogGateway(Protocol):
    async def search_catalog(
        self,
        *,
        query: str | None,
        category: str | None,
        min_price: float | None,
        max_price: float | None,
        only_in_stock: bool,
        limit: int,
    ) -> list[CatalogItem]: ...

    async def get_product(
        self, reference: str
    ) -> CatalogItem | None: ...


class OrderGateway(Protocol):
    async def list_orders(
        self,
        *,
        customer_id: int,
        status: str | None,
        limit: int,
    ) -> list[OrderSummary]: ...

    async def get_order(
        self, *, customer_id: int, reference: str
    ) -> OrderSummary | None: ...

    async def get_order_by_tracking(
        self, *, customer_id: int, tracking_code: str
    ) -> OrderSummary | None: ...


class ComplaintGateway(Protocol):
    async def register(
        self,
        *,
        conversation_id: int,
        customer_id: int,
        message_id: int,
        category: str,
        description: str,
        order_reference: str | None,
        priority: str,
    ) -> RegisteredComplaint: ...


class AgentContextPort(Protocol):
    async def claim(
        self, message_id: int
    ) -> ProcessingContext | None: ...

    async def history(
        self, conversation_id: int, *, limit: int
    ) -> list[HistoryMessage]: ...

    async def complete_turn(
        self,
        *,
        user_message_id: int,
        content: str,
        metadata: dict[str, Any],
        deliver_via_webhook: bool,
        is_fallback: bool = False,
    ) -> AppendedMessage: ...

    async def fail(self, message_id: int, *, error_code: str) -> None: ...

    async def release_for_retry(self, message_id: int) -> None: ...

    async def enqueue_webhook(self, assistant_message_id: int) -> None: ...


class DeliveryTargetPort(Protocol):
    async def get_target(
        self, assistant_message_id: int
    ) -> DeliveryTarget | None: ...

    async def update_delivery(
        self,
        assistant_message_id: int,
        *,
        status: str,
        attempts: int,
        error_code: str | None,
        delivered_at: Any | None,
    ) -> None: ...


class WebhookSender(Protocol):
    async def send(
        self,
        *,
        url: str,
        payload: dict[str, Any],
        timestamp: int,
    ) -> None: ...
