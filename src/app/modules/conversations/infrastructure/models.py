from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Identity, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.modules.conversations.domain.conversation import Conversation
from app.modules.conversations.domain.conversation_status import (
    ConversationStatus,
)


class ConversationModel(TimestampMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_customer_id", "customer_id"),
        Index(
            "ix_conversations_customer_created",
            "customer_id",
            "created_at",
        ),
    )

    conversation_id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    public_id: Mapped[UUID] = mapped_column(unique=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.customer_id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(
            ConversationStatus,
            name="conversation_status",
            native_enum=True,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        default=ConversationStatus.ACTIVE,
        server_default=ConversationStatus.ACTIVE.value,
    )
    awaiting_human: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    def to_domain(self) -> Conversation:
        return Conversation(
            conversation_id=self.conversation_id,
            public_id=self.public_id,
            customer_id=self.customer_id,
            status=self.status,
            awaiting_human=self.awaiting_human,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
