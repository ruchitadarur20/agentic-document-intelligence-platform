import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(40), default="analyst", index=True)
    api_key_hash: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    title: Mapped[str | None] = mapped_column(String(300))
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(30))
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(150))
    storage_uri: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(40), default="uploaded", index=True)
    checksum: Mapped[str] = mapped_column(String(128), index=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Embedding(Base, TimestampMixin):
    __tablename__ = "embeddings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), index=True)
    chunk_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    content: Mapped[str] = mapped_column(Text)
    embedding_model: Mapped[str] = mapped_column(String(200))
    vector: Mapped[list[float]] = mapped_column(JSON)
    chunk_metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    __table_args__ = (Index("ix_embeddings_doc_chunk", "document_id", "chunk_id"),)


class Evaluation(Base, TimestampMixin):
    __tablename__ = "evaluations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("runs.id"), nullable=True)
    relevance: Mapped[int] = mapped_column(Integer)
    faithfulness: Mapped[int] = mapped_column(Integer)
    completeness: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[int] = mapped_column(Integer)
    token_usage: Mapped[int] = mapped_column(Integer)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class PromptVersion(Base, TimestampMixin):
    __tablename__ = "prompt_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), index=True)
    version: Mapped[str] = mapped_column(String(80))
    template: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Experiment(Base, TimestampMixin):
    __tablename__ = "experiments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(250), index=True)
    variant: Mapped[str] = mapped_column(String(120))
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)


class Run(Base, TimestampMixin):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("conversations.id"))
    status: Mapped[str] = mapped_column(String(40), default="running", index=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), index=True)
    plan: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
