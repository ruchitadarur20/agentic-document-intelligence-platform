from typing import Any, TypedDict
from uuid import UUID

from app.services.vector_store import RetrievedChunk


class AgentState(TypedDict, total=False):
    query: str
    conversation_id: UUID
    run_id: UUID
    metadata_filters: dict[str, Any]
    plan: dict[str, Any]
    retrieved_chunks: list[RetrievedChunk]
    ranked_chunks: list[RetrievedChunk]
    answer: str
    citations: list[dict[str, Any]]
    validation: dict[str, Any]
    evaluation: dict[str, Any]
    llmops: dict[str, Any]
    latency_ms: int
    token_usage: int
