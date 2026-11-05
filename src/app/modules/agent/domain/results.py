from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Citation:
    source_type: str
    reference: str


@dataclass(frozen=True, slots=True)
class ToolResult:
    ok: bool
    data: Any = None
    citations: tuple[Citation, ...] = ()
    error_code: str | None = None
    error_message: str | None = None
    tool_name: str = ""
    trace_payload: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        if self.ok:
            return {
                "ok": True,
                "data": self.data,
                "citations": [
                    {
                        "source_type": citation.source_type,
                        "reference": citation.reference,
                    }
                    for citation in self.citations
                ],
            }
        return {
            "ok": False,
            "error": {
                "code": self.error_code or "tool_error",
                "message": self.error_message or "Tool execution failed",
            },
        }


@dataclass(frozen=True, slots=True)
class KnowledgePassage:
    reference: str
    title: str
    path: str
    content: str
    score: float = 0.0
    document_name: str = ""


@dataclass(frozen=True, slots=True)
class CatalogPromotion:
    promotion_id: int
    discount_percent: int
    description: str | None
    starts_at: str | None = None
    ends_at: str | None = None


@dataclass(frozen=True, slots=True)
class CatalogItem:
    product_id: int
    name: str
    category: str
    price_brl: float
    effective_price_brl: float
    stock_quantity: int
    status: str
    description: str | None
    promotions: tuple[CatalogPromotion, ...] = ()
    specs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class OrderItemSummary:
    product_id: int
    product_name: str | None
    quantity: int
    is_final_sale: bool = False
    is_customized: bool = False
    is_hygiene_restricted: bool = False


@dataclass(frozen=True, slots=True)
class OrderSummary:
    order_id: int
    status: str
    total_brl: float
    payment_method: str
    order_date: str
    sales_channel: str | None
    tracking_code: str | None
    estimated_delivery: str | None
    delivered_at: str | None
    items: tuple[OrderItemSummary, ...] = ()


@dataclass(frozen=True, slots=True)
class RegisteredComplaint:
    public_id: str
    status: str
    category: str
    already_open: bool = False


@dataclass(frozen=True, slots=True)
class WriterAnswer:
    message: str
    citations: tuple[Citation, ...] = ()
    needs_human_handoff: bool = False
    follow_up_question: str | None = None
    confidence: str = "medium"


@dataclass(frozen=True, slots=True)
class OrchestratorOutcome:
    note: str
    tool_results: tuple[ToolResult, ...] = ()
    iterations: int = 0
    max_iterations_reached: bool = False
