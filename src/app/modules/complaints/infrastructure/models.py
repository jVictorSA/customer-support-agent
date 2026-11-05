from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Identity, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.modules.complaints.domain.complaint import Complaint
from app.modules.complaints.domain.complaint_enums import (
    ComplaintCategory,
    ComplaintPriority,
    ComplaintStatus,
)


class ComplaintModel(TimestampMixin, Base):
    __tablename__ = "complaints"
    __table_args__ = (
        Index("ix_complaints_customer_status", "customer_id", "status"),
        Index("ix_complaints_conversation_status", "conversation_id", "status"),
    )

    complaint_id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    public_id: Mapped[UUID] = mapped_column(unique=True, nullable=False)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.customer_id", ondelete="RESTRICT"),
        nullable=False,
    )
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.message_id", ondelete="SET NULL"),
        nullable=True,
    )
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.order_id", ondelete="SET NULL"),
        nullable=True,
    )
    category: Mapped[ComplaintCategory] = mapped_column(
        Enum(
            ComplaintCategory,
            name="complaint_category",
            native_enum=True,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[ComplaintPriority] = mapped_column(
        Enum(
            ComplaintPriority,
            name="complaint_priority",
            native_enum=True,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        default=ComplaintPriority.NORMAL,
        server_default=ComplaintPriority.NORMAL.value,
    )
    status: Mapped[ComplaintStatus] = mapped_column(
        Enum(
            ComplaintStatus,
            name="complaint_status",
            native_enum=True,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        default=ComplaintStatus.OPEN,
        server_default=ComplaintStatus.OPEN.value,
    )

    def to_domain(self) -> Complaint:
        return Complaint(
            complaint_id=self.complaint_id,
            public_id=self.public_id,
            conversation_id=self.conversation_id,
            customer_id=self.customer_id,
            message_id=self.message_id,
            order_id=self.order_id,
            category=self.category,
            description=self.description,
            priority=self.priority,
            status=self.status,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
