from typing import Any
from uuid import UUID

from app.core.config import settings


class MetadataStore:
    def __init__(self) -> None:
        self._client = None

    def _collection(self, name: str):
        if self._client is None:
            from motor.motor_asyncio import AsyncIOMotorClient

            self._client = AsyncIOMotorClient(settings.mongo_url)
        return self._client[settings.mongo_database][name]

    async def save_raw_document_metadata(self, document_id: UUID, metadata: dict[str, Any]) -> None:
        try:
            await self._collection("raw_document_metadata").update_one(
                {"document_id": str(document_id)},
                {"$set": {"document_id": str(document_id), **metadata}},
                upsert=True,
            )
        except Exception:
            return

    async def save_chunk_metadata(self, document_id: UUID, chunks: list[dict[str, Any]]) -> None:
        if not chunks:
            return
        try:
            operations = [
                {
                    "document_id": str(document_id),
                    "chunk_id": chunk["chunk_id"],
                    **chunk.get("metadata", {}),
                }
                for chunk in chunks
            ]
            collection = self._collection("chunk_metadata")
            for item in operations:
                await collection.update_one(
                    {"chunk_id": item["chunk_id"]},
                    {"$set": item},
                    upsert=True,
                )
        except Exception:
            return

