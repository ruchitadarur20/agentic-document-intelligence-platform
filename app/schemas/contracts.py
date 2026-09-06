from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic import ConfigDict


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    content_type: str
    status: str
    checksum: str
    page_count: int
    metadata_json: dict[str, Any]
    created_at: datetime


class UploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: UUID
    status: str
    checksum: str


class ProcessRequest(BaseModel):
    document_id: UUID
    force: bool = False


class ProcessResponse(BaseModel):
    document_id: UUID
    status: str
    chunk_count: int


class ChatRequest(BaseModel):
    query: str = Field(min_length=1)
    conversation_id: UUID | None = None
    user_id: UUID | None = None
    metadata_filters: dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    document_id: UUID | None = None
    chunk_id: str
    filename: str | None = None
    excerpt: str
    source_url: str | None = None


class ChatResponse(BaseModel):
    conversation_id: UUID
    run_id: UUID
    answer: str
    citations: list[Citation]
    validation: dict[str, Any]
    evaluation: dict[str, Any]


class AgentRunRequest(ChatRequest):
    dry_run: bool = False


class EvaluationRequest(BaseModel):
    query: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    latency_ms: int = 0
    token_usage: int = 0


class EvaluationResponse(BaseModel):
    relevance: int
    faithfulness: int
    completeness: int
    latency_ms: int
    token_usage: int
    details: dict[str, Any]
