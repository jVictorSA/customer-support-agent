"""create document ingestion tables

Revision ID: c91a17e0c3a0
Revises: 1956eca4bb8a
Create Date: 2026-11-04 18:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from app.modules.documents.infrastructure.types import Ltree

revision: str = "c91a17e0c3a0"
down_revision: Union[str, Sequence[str], None] = "1956eca4bb8a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

document_status = postgresql.ENUM(
    "pending",
    "processing",
    "completed",
    "failed",
    name="document_status",
    create_type=False,
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS ltree")
    document_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "documents",
        sa.Column("document_id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column(
            "source_content_type", sa.String(length=100), nullable=False
        ),
        sa.Column("source_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("status", document_status, nullable=False),
        sa.Column("processing_stage", sa.String(length=32), nullable=True),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "deleted_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("total_pages", sa.Integer(), nullable=True),
        sa.Column(
            "section_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "chunk_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("parser_version", sa.String(length=64), nullable=True),
        sa.Column("chunking_version", sa.String(length=64), nullable=True),
        sa.Column("summary_version", sa.String(length=64), nullable=True),
        sa.Column("embedding_model", sa.String(length=128), nullable=True),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=True),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column(
            "last_error_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
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
        sa.UniqueConstraint("public_id", name="uq_documents_public_id"),
        sa.UniqueConstraint("source_checksum", name="uq_documents_source_checksum"),
    )
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_documents_created_at", "documents", ["created_at"])

    op.create_table(
        "document_sections",
        sa.Column("section_id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("parent_section_id", sa.Integer(), nullable=True),
        sa.Column("section_number", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("path", Ltree(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("summary_embedding", Vector(1024), nullable=True),
        sa.Column(
            "token_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("start_page", sa.Integer(), nullable=False),
        sa.Column("end_page", sa.Integer(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
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
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.document_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_section_id"],
            ["document_sections.section_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("public_id", name="uq_document_sections_public_id"),
        sa.UniqueConstraint("document_id", "path", name="uq_document_sections_document_id"),
    )
    op.create_index(
        "ix_document_sections_document_id",
        "document_sections",
        ["document_id"],
    )
    op.create_index(
        "ix_document_sections_parent_section_id",
        "document_sections",
        ["parent_section_id"],
    )
    op.create_index(
        "ix_document_sections_path_gist",
        "document_sections",
        ["path"],
        postgresql_using="gist",
    )
    op.create_index(
        "ix_document_sections_summary_embedding_hnsw",
        "document_sections",
        ["summary_embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"summary_embedding": "vector_cosine_ops"},
    )

    op.create_table(
        "document_chunks",
        sa.Column("chunk_id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("public_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("section_id", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding_text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding_text_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("start_page", sa.Integer(), nullable=False),
        sa.Column("end_page", sa.Integer(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
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
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.document_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["section_id"],
            ["document_sections.section_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("public_id", name="uq_document_chunks_public_id"),
        sa.UniqueConstraint("section_id", "chunk_index", name="uq_document_chunks_section_id"),
    )
    op.execute(
        "ALTER TABLE document_chunks ADD COLUMN search_vector tsvector "
        "GENERATED ALWAYS AS "
        "(to_tsvector('portuguese', coalesce(content, ''))) STORED"
    )
    op.create_index(
        "ix_document_chunks_document_id", "document_chunks", ["document_id"]
    )
    op.create_index(
        "ix_document_chunks_section_id", "document_chunks", ["section_id"]
    )
    op.create_index(
        "ix_document_chunks_embedding_hnsw",
        "document_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_document_chunks_search_vector_gin",
        "document_chunks",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_chunks_search_vector_gin", table_name="document_chunks"
    )
    op.drop_index(
        "ix_document_chunks_embedding_hnsw", table_name="document_chunks"
    )
    op.drop_index("ix_document_chunks_section_id", table_name="document_chunks")
    op.drop_index(
        "ix_document_chunks_document_id", table_name="document_chunks"
    )
    op.drop_table("document_chunks")

    op.drop_index(
        "ix_document_sections_summary_embedding_hnsw",
        table_name="document_sections",
    )
    op.drop_index(
        "ix_document_sections_path_gist", table_name="document_sections"
    )
    op.drop_index(
        "ix_document_sections_parent_section_id",
        table_name="document_sections",
    )
    op.drop_index(
        "ix_document_sections_document_id", table_name="document_sections"
    )
    op.drop_table("document_sections")

    op.drop_index("ix_documents_created_at", table_name="documents")
    op.drop_index("ix_documents_status", table_name="documents")
    op.drop_table("documents")

    document_status.drop(op.get_bind(), checkfirst=True)
