from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class IntentKind(StrEnum):
    GREETING = "greeting"
    STORE_INFO = "store_info"
    POLICY = "policy"
    PRODUCT_SEARCH = "product_search"
    ORDER_STATUS = "order_status"
    COMPLAINT = "complaint"
    OUT_OF_SCOPE = "out_of_scope"
    SMALLTALK = "smalltalk"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class Intent:
    primary_intent: IntentKind
    secondary_intents: tuple[IntentKind, ...] = ()
    entities: dict[str, Any] = field(default_factory=dict)
    needs_knowledge: bool = False
    needs_operational_data: bool = False
    wants_complaint: bool = False
    out_of_scope: bool = False
    out_of_scope_type: str = "none"
    urgency: str = "normal"
    missing_information: tuple[str, ...] = ()
