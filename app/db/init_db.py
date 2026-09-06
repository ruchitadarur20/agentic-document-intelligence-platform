from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import settings
from app.db.base import Base
from app.models import entities  # noqa: F401


async def initialize_database(engine: AsyncEngine) -> None:
    if settings.app_env not in {"local", "test"}:
        return
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

