from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class AgentRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentStepType(StrEnum):
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    VALIDATION = "validation"


class AgentRunModel(TimestampMixin, Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("ix_agent_runs_conversation_created", "conversation_id", "created_at"),
        Index("ix_agent_runs_customer_created", "customer_id", "created_at"),
        Index("ix_agent_runs_status", "status"),
    )

    run_id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
        nullable=False,
    )
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.customer_id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.message_id", ondelete="CASCADE"),
        nullable=False,
    )
    assistant_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.message_id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[AgentRunStatus] = mapped_column(
        Enum(
            AgentRunStatus,
            name="agent_run_status",
            native_enum=True,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        default=AgentRunStatus.RUNNING,
        server_default=AgentRunStatus.RUNNING.value,
    )
    intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    latency_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    input_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    output_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    fallback_used: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default=text("false")
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AgentStepModel(TimestampMixin, Base):
    __tablename__ = "agent_steps"
    __table_args__ = (
        Index("ix_agent_steps_run_index", "run_id", "step_index"),
        Index("ix_agent_steps_agent_name", "agent_name"),
    )

    step_id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("agent_runs.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    step_type: Mapped[AgentStepType] = mapped_column(
        Enum(
            AgentStepType,
            name="agent_step_type",
            native_enum=True,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    tool_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_data: Mapped[dict[str, Any]] = mapped_column(
        "input",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    output_data: Mapped[dict[str, Any]] = mapped_column(
        "output",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    temperature: Mapped[float | None] = mapped_column(nullable=True)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    completion_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    latency_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    provider_request_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
