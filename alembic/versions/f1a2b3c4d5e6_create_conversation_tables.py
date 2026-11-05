"""create conversation, complaint and agent trace tables

Revision ID: f1a2b3c4d5e6
Revises: c91a17e0c3a0
Create Date: 2026-11-04 20:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "c91a17e0c3a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

conversation_status = postgresql.ENUM(
    "active", "closed", name="conversation_status", create_type=False
)
message_role = postgresql.ENUM(
    "user", "assistant", name="message_role", create_type=False
)
message_status = postgresql.ENUM(
    "queued", "processing", "completed", "failed",
    name="message_status",
    create_type=False,
)
delivery_status = postgresql.ENUM(
    "not_requested", "pending", "delivered", "failed",
    name="delivery_status",
    create_type=False,
)
complaint_category = postgresql.ENUM(
    "order", "product_defect", "delivery", "service", "other",
    name="complaint_category",
    create_type=False,
)
complaint_priority = postgresql.ENUM(
    "low", "normal", "high",
    name="complaint_priority",
    create_type=False,
)
complaint_status = postgresql.ENUM(
    "open", "in_progress", "resolved", "closed",
    name="complaint_status",
    create_type=False,
)
agent_run_status = postgresql.ENUM(
    "running", "completed", "failed",
    name="agent_run_status",
    create_type=False,
)
agent_step_type = postgresql.ENUM(
    "llm_call", "tool_call", "validation",
    name="agent_step_type",
    create_type=False,
)

_ENUMS = (
    conversation_status,
    message_role,
    message_status,
    delivery_status,
    complaint_category,
    complaint_priority,
    complaint_status,
    agent_run_status,
    agent_step_type,
)


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def upgrade() -> None:
    bind = op.get_bind()
    for enum in _ENUMS:
        enum.create(bind, checkfirst=True)

    op.create_table(
        "conversations",
        sa.Column("conversation_id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("public_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column(
            "customer_id",
            sa.Integer(),
            sa.ForeignKey("customers.customer_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            conversation_status,
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "awaiting_human",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        *_timestamps(),
    )
    op.create_index(
        "ix_conversations_customer_id", "conversations", ["customer_id"]
    )
    op.create_index(
        "ix_conversations_customer_created",
        "conversations",
        ["customer_id", "created_at"],
    )

    op.create_table(
        "messages",
        sa.Column("message_id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("public_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey(
                "conversations.conversation_id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column("role", message_role, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", message_status, nullable=False),
        sa.Column("client_message_id", sa.String(length=128), nullable=True),
        sa.Column(
            "reply_to_message_id",
            sa.Integer(),
            sa.ForeignKey("messages.message_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("webhook_url", sa.Text(), nullable=True),
        sa.Column(
            "delivery_status",
            delivery_status,
            nullable=False,
            server_default=sa.text("'not_requested'"),
        ),
        sa.Column(
            "delivery_attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "delivered_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "last_delivery_error_code",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column(
            "processing_started_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "processed_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        *_timestamps(),
    )
    op.create_index(
        "ix_messages_conversation_message",
        "messages",
        ["conversation_id", "message_id"],
    )
    op.create_index(
        "ix_messages_conversation_status",
        "messages",
        ["conversation_id", "status"],
    )
    op.create_index(
        "uq_messages_conversation_client_message",
        "messages",
        ["conversation_id", "client_message_id"],
        unique=True,
        postgresql_where=sa.text("client_message_id IS NOT NULL"),
    )

    op.create_table(
        "complaints",
        sa.Column("complaint_id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("public_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey(
                "conversations.conversation_id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.Integer(),
            sa.ForeignKey("customers.customer_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "message_id",
            sa.Integer(),
            sa.ForeignKey("messages.message_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "order_id",
            sa.Integer(),
            sa.ForeignKey("orders.order_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("category", complaint_category, nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("priority", complaint_priority, nullable=False, server_default=sa.text("'normal'")),
        sa.Column("status", complaint_status, nullable=False, server_default=sa.text("'open'")),
        *_timestamps(),
    )
    op.create_index(
        "ix_complaints_customer_status",
        "complaints",
        ["customer_id", "status"],
    )
    op.create_index(
        "ix_complaints_conversation_status",
        "complaints",
        ["conversation_id", "status"],
    )

    op.create_table(
        "agent_runs",
        sa.Column("run_id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey(
                "conversations.conversation_id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.Integer(),
            sa.ForeignKey("customers.customer_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "user_message_id",
            sa.Integer(),
            sa.ForeignKey("messages.message_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assistant_message_id",
            sa.Integer(),
            sa.ForeignKey("messages.message_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            agent_run_status,
            nullable=False,
            server_default=sa.text("'running'"),
        ),
        sa.Column("intent", sa.String(length=64), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "latency_ms",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "input_tokens",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "output_tokens",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "fallback_used",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        *_timestamps(),
    )
    op.create_index(
        "ix_agent_runs_conversation_created",
        "agent_runs",
        ["conversation_id", "created_at"],
    )
    op.create_index(
        "ix_agent_runs_customer_created",
        "agent_runs",
        ["customer_id", "created_at"],
    )
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])

    op.create_table(
        "agent_steps",
        sa.Column("step_id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("agent_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("agent_name", sa.String(length=64), nullable=False),
        sa.Column("step_type", agent_step_type, nullable=False),
        sa.Column("tool_name", sa.String(length=64), nullable=True),
        sa.Column(
            "input",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "output",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column(
            "prompt_tokens",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "completion_tokens",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "latency_ms",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "provider_request_id", sa.String(length=128), nullable=True
        ),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        *_timestamps(),
    )
    op.create_index(
        "ix_agent_steps_run_index",
        "agent_steps",
        ["run_id", "step_index"],
    )
    op.create_index(
        "ix_agent_steps_agent_name", "agent_steps", ["agent_name"]
    )


def downgrade() -> None:
    op.drop_table("agent_steps")
    op.drop_table("agent_runs")
    op.drop_table("complaints")
    op.drop_table("messages")
    op.drop_table("conversations")
    bind = op.get_bind()
    for enum in reversed(_ENUMS):
        enum.drop(bind, checkfirst=True)
