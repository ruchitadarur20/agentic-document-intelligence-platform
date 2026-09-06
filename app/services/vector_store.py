import math
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Embedding


@dataclass
class RetrievedChunk:
    chunk_id: str
    content: str
    score: float
    document_id: UUID | None = None
    metadata: dict[str, Any] | None = None


class VectorStore:
    async def delete_document_chunks(self, session: AsyncSession, document_id: UUID) -> None:
        await session.execute(delete(Embedding).where(Embedding.document_id == document_id))
        await session.commit()

    async def add_chunks(
        self,
        session: AsyncSession,
        document_id: UUID,
        chunks: list[dict[str, Any]],
        vectors: list[list[float]],
        model: str,
    ) -> None:
        for chunk, vector in zip(chunks, vectors, strict=True):
            session.add(
                Embedding(
                    document_id=document_id,
                    chunk_id=chunk["chunk_id"],
                    content=chunk["text"],
                    embedding_model=model,
                    vector=vector,
                    chunk_metadata=chunk.get("metadata", {}),
                )
            )
        await session.commit()

    async def search(
        self,
        session: AsyncSession,
        query_vector: list[float],
        query_text: str,
        top_k: int,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[RetrievedChunk]:
        result = await session.execute(select(Embedding))
        rows = result.scalars().all()
        scored: list[RetrievedChunk] = []
        terms = {term.lower() for term in query_text.split() if len(term) > 2}
        for row in rows:
            if metadata_filters and not self._metadata_matches(row.chunk_metadata, metadata_filters):
                continue
            semantic = self._cosine(query_vector, row.vector)
            keyword = self._keyword_score(row.content, terms)
            scored.append(
                RetrievedChunk(
                    chunk_id=row.chunk_id,
                    content=row.content,
                    score=(0.75 * semantic) + (0.25 * keyword),
                    document_id=row.document_id,
                    metadata=row.chunk_metadata,
                )
            )
        return sorted(scored, key=lambda item: item.score, reverse=True)[:top_k]

    def _cosine(self, left: list[float], right: list[float]) -> float:
        limit = min(len(left), len(right))
        if limit == 0:
            return 0.0
        numerator = sum(left[i] * right[i] for i in range(limit))
        left_norm = math.sqrt(sum(left[i] * left[i] for i in range(limit))) or 1.0
        right_norm = math.sqrt(sum(right[i] * right[i] for i in range(limit))) or 1.0
        return numerator / (left_norm * right_norm)

    def _keyword_score(self, content: str, terms: set[str]) -> float:
        if not terms:
            return 0.0
        haystack = content.lower()
        matches = sum(1 for term in terms if term in haystack)
        return matches / len(terms)

    def _metadata_matches(self, metadata: dict[str, Any], filters: dict[str, Any]) -> bool:
        return all(metadata.get(key) == value for key, value in filters.items())
