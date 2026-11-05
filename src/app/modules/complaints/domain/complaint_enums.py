from enum import StrEnum


class ComplaintCategory(StrEnum):
    ORDER = "order"
    PRODUCT_DEFECT = "product_defect"
    DELIVERY = "delivery"
    SERVICE = "service"
    OTHER = "other"


class ComplaintPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class ComplaintStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
