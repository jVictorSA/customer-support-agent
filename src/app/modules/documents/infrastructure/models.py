from datetime import datetime
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Computed,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.modules.documents.domain.document import Document
from app.modules.documents.domain.document_status import DocumentStatus
from app.modules.documents.domain.section import DocumentSection
from app.modules.documents.infrastructure.types import Ltree

EMBEDDING_DIMENSIONS = 1024


class DocumentModel(TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_status", "status"),
        Index("ix_documents_created_at", "created_at"),
    )

    document_id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    public_id: Mapped[UUID] = mapped_column(unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_checksum: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(
            DocumentStatus,
            name="document_status",
            native_enum=True,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    processing_stage: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    is_enabled: Mapped[bool] = mapped_column(
        nullable=False, default=True, server_default=text("true")
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    total_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    parser_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chunking_version: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    summary_version: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    embedding_model: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    embedding_dimensions: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    last_error_code: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    last_error_at: Mapped[datetime | None] = mapped_column(
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

    sections: Mapped[list["DocumentSectionModel"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    chunks: Mapped[list["DocumentChunkModel"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def to_domain(self) -> Document:
        return Document(
            document_id=self.document_id,
            public_id=self.public_id,
            name=self.name,
            source_filename=self.source_filename,
            source_content_type=self.source_content_type,
            source_size_bytes=self.source_size_bytes,
            source_checksum=self.source_checksum,
            storage_key=self.storage_key,
            status=self.status,
            processing_stage=self.processing_stage,
            is_enabled=self.is_enabled,
            deleted_at=self.deleted_at,
            total_pages=self.total_pages,
            section_count=self.section_count,
            chunk_count=self.chunk_count,
            parser_version=self.parser_version,
            chunking_version=self.chunking_version,
            summary_version=self.summary_version,
            embedding_model=self.embedding_model,
            embedding_dimensions=self.embedding_dimensions,
            attempt_count=self.attempt_count,
            last_error_code=self.last_error_code,
            last_error_at=self.last_error_at,
            processed_at=self.processed_at,
            metadata=self.metadata_,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class DocumentSectionModel(TimestampMixin, Base):
    __tablename__ = "document_sections"
    __table_args__ = (
        UniqueConstraint("document_id", "path"),
        Index("ix_document_sections_document_id", "document_id"),
        Index("ix_document_sections_parent_section_id", "parent_section_id"),
        Index(
            "ix_document_sections_path_gist",
            "path",
            postgresql_using="gist",
        ),
        Index(
            "ix_document_sections_summary_embedding_hnsw",
            "summary_embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"summary_embedding": "vector_cosine_ops"},
        ),
    )

    section_id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    public_id: Mapped[UUID] = mapped_column(unique=True, nullable=False)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.document_id", ondelete="CASCADE"),
        nullable=False,
    )
    parent_section_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_sections.section_id", ondelete="CASCADE"),
        nullable=True,
    )
    section_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    path: Mapped[str] = mapped_column(Ltree, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIMENSIONS), nullable=True
    )
    token_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    start_page: Mapped[int] = mapped_column(Integer, nullable=False)
    end_page: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    document: Mapped[DocumentModel] = relationship(back_populates="sections")
    parent: Mapped["DocumentSectionModel | None"] = relationship(
        remote_side="DocumentSectionModel.section_id"
    )
    chunks: Mapped[list["DocumentChunkModel"]] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def to_domain(self, parent_public_id: UUID | None) -> DocumentSection:
        return DocumentSection(
            section_id=self.section_id,
            public_id=self.public_id,
            document_id=self.document_id,
            parent_section_id=self.parent_section_id,
            parent_public_id=parent_public_id,
            section_number=self.section_number,
            title=self.title,
            level=self.level,
            path=self.path,
            position=self.position,
            content=self.content,
            summary=self.summary,
            summary_embedding=self.summary_embedding,
            token_count=self.token_count,
            start_page=self.start_page,
            end_page=self.end_page,
            metadata=self.metadata_,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class DocumentChunkModel(TimestampMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("section_id", "chunk_index"),
        Index("ix_document_chunks_document_id", "document_id"),
        Index("ix_document_chunks_section_id", "section_id"),
        Index(
            "ix_document_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index(
            "ix_document_chunks_search_vector_gin",
            "search_vector",
            postgresql_using="gin",
        ),
    )

    chunk_id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    public_id: Mapped[UUID] = mapped_column(unique=True, nullable=False)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.document_id", ondelete="CASCADE"),
        nullable=False,
    )
    section_id: Mapped[int] = mapped_column(
        ForeignKey("document_sections.section_id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_text_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIMENSIONS), nullable=True
    )
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    start_page: Mapped[int] = mapped_column(Integer, nullable=False)
    end_page: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('portuguese', coalesce(content, ''))",
            persisted=True,
        ),
        nullable=True,
    )

    document: Mapped[DocumentModel] = relationship(back_populates="chunks")
    section: Mapped[DocumentSectionModel] = relationship(
        back_populates="chunks"
    )
