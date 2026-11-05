from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.modules.messages.domain.message import Message
from app.modules.messages.domain.message_enums import (
    DeliveryStatus,
    MessageRole,
    MessageStatus,
)


class MessageModel(TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_message", "conversation_id", "message_id"),
        Index("ix_messages_conversation_status", "conversation_id", "status"),
        Index(
            "uq_messages_conversation_client_message",
            "conversation_id",
            "client_message_id",
            unique=True,
            postgresql_where=text("client_message_id IS NOT NULL"),
        ),
    )

    message_id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    public_id: Mapped[UUID] = mapped_column(unique=True, nullable=False)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(
            MessageRole,
            name="message_role",
            native_enum=True,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[MessageStatus] = mapped_column(
        Enum(
            MessageStatus,
            name="message_status",
            native_enum=True,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    client_message_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    reply_to_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.message_id", ondelete="SET NULL"),
        nullable=True,
    )
    webhook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_status: Mapped[DeliveryStatus] = mapped_column(
        Enum(
            DeliveryStatus,
            name="delivery_status",
            native_enum=True,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        default=DeliveryStatus.NOT_REQUESTED,
        server_default=DeliveryStatus.NOT_REQUESTED.value,
    )
    delivery_attempts: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default=text("0")
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_delivery_error_code: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    reply_to: Mapped["MessageModel | None"] = relationship(
        remote_side="MessageModel.message_id"
    )

    def to_domain(self) -> Message:
        reply_to = self.__dict__.get("reply_to")
        return Message(
            message_id=self.message_id,
            public_id=self.public_id,
            conversation_id=self.conversation_id,
            role=self.role,
            content=self.content,
            status=self.status,
            client_message_id=self.client_message_id,
            reply_to_message_id=self.reply_to_message_id,
            reply_to_public_id=(
                reply_to.public_id if reply_to is not None else None
            ),
            webhook_url=self.webhook_url,
            delivery_status=self.delivery_status,
            delivery_attempts=self.delivery_attempts,
            delivered_at=self.delivered_at,
            last_delivery_error_code=self.last_delivery_error_code,
            error_code=self.error_code,
            processing_started_at=self.processing_started_at,
            processed_at=self.processed_at,
            metadata=self.metadata_,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
