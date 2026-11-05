from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.complaints.domain.complaint_enums import (
    ComplaintCategory,
    ComplaintPriority,
    ComplaintStatus,
)


@dataclass(frozen=True, slots=True)
class Complaint:
    complaint_id: int | None
    public_id: UUID
    conversation_id: int
    customer_id: int
    message_id: int | None
    order_id: int | None
    category: ComplaintCategory
    description: str
    priority: ComplaintPriority = ComplaintPriority.NORMAL
    status: ComplaintStatus = ComplaintStatus.OPEN
    created_at: datetime | None = None
    updated_at: datetime | None = None
