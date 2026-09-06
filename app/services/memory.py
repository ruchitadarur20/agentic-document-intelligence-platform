from uuid import UUID

from app.core.config import settings


class ConversationMemory:
    def __init__(self) -> None:
        self._redis = None

    async def _client(self):
        if self._redis is None:
            from redis.asyncio import from_url

            self._redis = from_url(settings.redis_url, decode_responses=True)
        return self._redis

    async def append(self, conversation_id: UUID, role: str, content: str) -> None:
        try:
            redis = await self._client()
            key = f"conversation:{conversation_id}:messages"
            await redis.rpush(key, f"{role}:{content}")
            await redis.ltrim(key, -100, -1)
        except Exception:
            return

    async def read(self, conversation_id: UUID, limit: int = 20) -> list[str]:
        try:
            redis = await self._client()
            return await redis.lrange(f"conversation:{conversation_id}:messages", -limit, -1)
        except Exception:
            return []

