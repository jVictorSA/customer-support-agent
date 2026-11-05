from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.modules.complaints.domain.complaint import Complaint
from app.modules.complaints.domain.complaint_enums import (
    ComplaintCategory,
    ComplaintPriority,
    ComplaintStatus,
)


class ComplaintResponse(BaseModel):
    public_id: UUID
    category: ComplaintCategory
    description: str
    priority: ComplaintPriority
    status: ComplaintStatus
    order_id: int | None
    created_at: datetime

    @classmethod
    def from_domain(cls, complaint: Complaint) -> "ComplaintResponse":
        assert complaint.created_at is not None
        return cls(
            public_id=complaint.public_id,
            category=complaint.category,
            description=complaint.description,
            priority=complaint.priority,
            status=complaint.status,
            order_id=complaint.order_id,
            created_at=complaint.created_at,
        )
