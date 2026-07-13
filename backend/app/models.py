"""ORM models: standard RAG entities + security testbed entities."""
from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .config import settings
from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String)
    doc_type: Mapped[str] = mapped_column(String, default="text")
    # access_tags feed metadata pre-filtering; "clean"/"poisoned" label feeds the corpus
    access_tags: Mapped[list] = mapped_column(JSONB, default=list)
    corpus_label: Mapped[str] = mapped_column(String, default="clean")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    # provenance: required for citations AND VectorGuard local RAG scan metadata
    section_path: Mapped[str] = mapped_column(String, default="")
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    char_offset: Mapped[int] = mapped_column(Integer, default=0)
    # contextual retrieval prepends title/section context before this text
    contextual_prefix: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    corpus_label: Mapped[str] = mapped_column(String, default="clean", index=True)

    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dim), nullable=True
    )
    tsv: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)

    document: Mapped["Document"] = relationship(back_populates="chunks")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    title: Mapped[str] = mapped_column(String, default="New conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String)  # user | assistant | system
    content: Mapped[str] = mapped_column(Text)
    mode: Mapped[str | None] = mapped_column(String, nullable=True)
    retrieved_chunk_ids: Mapped[list] = mapped_column(JSONB, default=list)
    token_usage: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class SecurityTestRun(Base):
    __tablename__ = "security_test_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    mode: Mapped[str] = mapped_column(String)  # naive | hardened
    vectorguard_suite: Mapped[str] = mapped_column(String)
    pass_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    risk_score_total: Mapped[float] = mapped_column(Float, default=0.0)
    findings: Mapped[dict] = mapped_column(JSONB, default=dict)
    git_commit_sha: Mapped[str | None] = mapped_column(String, nullable=True)
    run_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Canary(Base):
    __tablename__ = "canaries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    # secret_token | policy_name | internal_email | system_marker
    value_type: Mapped[str] = mapped_column(String)
    value_hash: Mapped[str] = mapped_column(String)
    planted_location: Mapped[str] = mapped_column(String)  # system_prompt | document:{id}
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
